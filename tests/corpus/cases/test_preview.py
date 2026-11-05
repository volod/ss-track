"""`corpus preview` on staged bundles: identical bytes, the outline, and a removed frame."""

import hashlib
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK
from ss_track.corpus import ImportResult, open_frame_bundle
from ss_track.corpus.cases.preview import ROLE_CASE, ROLE_PARENT, ROLE_REMOVED
from ss_track.corpus.cases.preview_png import OUTLINE_RGB, REMOVED_RGB
from tests.corpus._media import HEIGHT, WIDTH
from tests.corpus.cases._staged_cases import CORPUS, stage_cases
from tests.corpus.cases.test_preview_png import _png_rgb
from tests.corpus.conftest import (
    WriteCorpus,
    case_of,
    last_record,
)

_REGION = {"x": 4, "y": 3, "width": 10, "height": 8}
_ABSENCE_WINDOW = {"start_frame": 4, "end_frame": 6}
_DROP_WINDOW = {"start_frame": 0, "end_frame": 2}
_OUTLINE = bytes(OUTLINE_RGB)
_REMOVED = bytes(REMOVED_RGB)


def _cases() -> list[dict[str, object]]:
    absence = {"region": _REGION, "plate_frame": 0, "noise": 0}
    return [
        case_of("absence", "target_absence", 1, absence, window=_ABSENCE_WINDOW),
        case_of("dropped", "dropped_frames", 1, {"count": 1}, window=_DROP_WINDOW),
    ]


def _pixel(packed: bytes, width: int, x: int, y: int) -> bytes:
    start = (y * width + x) * 3
    return packed[start : start + 3]


def _perimeter(region: dict[str, int]) -> set[tuple[int, int]]:
    x0, y0 = region["x"], region["y"]
    x1 = x0 + region["width"] - 1
    y1 = y0 + region["height"] - 1
    top = {(x, y0) for x in range(x0, x1 + 1)}
    bottom = {(x, y1) for x in range(x0, x1 + 1)}
    left = {(x0, y) for y in range(y0, y1 + 1)}
    right = {(x1, y) for y in range(y0, y1 + 1)}
    return top | bottom | left | right


def _removed_index(root: Path) -> int:
    parent = open_frame_bundle(root / "one")
    dropped = open_frame_bundle(root / "dropped")
    held = {entry.frame_index for entry in dropped.entries}
    return next(index for index in parent.selection if index not in held)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def staged(imported: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> Path:
    return stage_cases(imported, write_corpus, data_root, *_cases())


def _expect_sheet_record(record: dict[str, object], digest: str) -> None:
    assert record["status"] == "written"
    preview = record["preview"]
    assert isinstance(preview, dict)
    assert preview["encoder"] == "stored-deflate-rgb24-v1"
    assert preview["frame_index"] == 4
    assert preview["frame_width"] == WIDTH
    assert preview["width"] == WIDTH * 3
    assert preview["png_sha256"] == digest
    panels = preview["panels"]
    assert isinstance(panels, list)
    assert [panel["role"] for panel in panels] == [ROLE_PARENT, ROLE_CASE, ROLE_CASE]
    assert panels[1]["region"] == _REGION
    assert "region" not in panels[2]


def _expect_sheet_pixels(staged: Path, payload: bytes) -> None:
    width, height, pixels = _png_rgb(payload)
    assert (width, height) == (WIDTH * 3, HEIGHT)
    parent = open_frame_bundle(staged / "one").read_frame(4)
    absence = open_frame_bundle(staged / "absence").read_frame(4)
    dropped = open_frame_bundle(staged / "dropped").read_frame(4)
    assert _pixel(absence, WIDTH, 4, 3) != _OUTLINE
    outlined = _perimeter(_REGION)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            assert _pixel(pixels, width, x, y) == _pixel(parent, WIDTH, x, y)
            shown = _pixel(pixels, width, WIDTH + x, y)
            raw = _pixel(absence, WIDTH, x, y)
            assert shown == (_OUTLINE if (x, y) in outlined else raw)
            assert _pixel(pixels, width, 2 * WIDTH + x, y) == _pixel(dropped, WIDTH, x, y)


def test_the_sheet_matches_twice_and_outlines_only_the_declared_pixels(
    staged: Path, cli_root: Path, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    before = _snapshot(staged)
    out = tmp_path / "sheet.png"
    again = tmp_path / "again.png"
    command = ["corpus", "preview", "--corpus", CORPUS, "--stream", "one", "--frame", "4"]

    assert main([*command, "--out", str(out)]) == EXIT_OK
    assert main([*command, "--out", str(again)]) == EXIT_OK
    first = out.read_bytes()
    assert first == again.read_bytes()
    _expect_sheet_record(last_record(caplog), hashlib.sha256(first).hexdigest())
    _expect_sheet_pixels(staged, first)
    assert _snapshot(staged) == before


def test_a_removed_frame_is_marked_in_place(
    staged: Path, cli_root: Path, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    index = _removed_index(staged)
    out = tmp_path / "removed.png"
    assert index in range(0, 2)

    assert (
        main(
            [
                "corpus",
                "preview",
                "--corpus",
                CORPUS,
                "--stream",
                "one",
                "--frame",
                str(index),
                "--out",
                str(out),
            ]
        )
        == EXIT_OK
    )

    preview = last_record(caplog)["preview"]
    assert isinstance(preview, dict)
    assert [panel["role"] for panel in preview["panels"]] == [ROLE_PARENT, ROLE_CASE, ROLE_REMOVED]
    assert "region" not in preview["panels"][1]
    _, _, pixels = _png_rgb(out.read_bytes())
    absence = open_frame_bundle(staged / "absence").read_frame(index)
    width = WIDTH * 3
    for y in range(HEIGHT):
        for x in range(WIDTH):
            assert _pixel(pixels, width, WIDTH + x, y) == _pixel(absence, WIDTH, x, y)
            assert _pixel(pixels, width, 2 * WIDTH + x, y) == _REMOVED
