"""Refusals and edges of `corpus preview`: nothing is written, and a gap stays visible."""

import os
import shutil
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    open_frame_bundle,
    stage_corpus,
)
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.cases.preview import (
    ROLE_PARENT,
    _require_rgb24,
    _require_same_shape,
    _write_bytes,
)
from ss_track.corpus.decoding.pixels import OUTPUT_PIXEL_FORMAT
from tests.corpus._media import HEIGHT, WIDTH
from tests.corpus.cases._staged_cases import CORPUS, stage_cases
from tests.corpus.cases.test_preview import _cases, _snapshot
from tests.corpus.cases.test_preview_png import _png_rgb
from tests.corpus.conftest import WriteCorpus, last_record, stream_of


def _preview(frame: str, stream: str, out: Path) -> int:
    return main(
        [
            "corpus",
            "preview",
            "--corpus",
            CORPUS,
            "--stream",
            stream,
            "--frame",
            frame,
            "--out",
            str(out),
        ]
    )


def _bundle(**overrides: object) -> FrameBundle:
    fields: dict[str, object] = {
        "directory": Path("."),
        "stream_id": "one",
        "corpus_manifest_sha256": "a" * 64,
        "bundle_sha256": "b" * 64,
        "source_sha256": "c" * 64,
        "pixel_format": OUTPUT_PIXEL_FORMAT,
        "width": WIDTH,
        "height": HEIGHT,
        "time_base": None,
        "timestamp_quality": "missing",
        "capture_clock_evidence": None,
        "selection": range(1),
        "entries": (),
        "transform": "identity",
        "parent_bundle_sha256": None,
    }
    return FrameBundle(**(fields | overrides))  # type: ignore[arg-type]


@pytest.fixture
def staged(imported: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> Path:
    return stage_cases(imported, write_corpus, data_root, *_cases())


def _refuse_bad_inputs(
    staged: Path, caplog: pytest.LogCaptureFixture, tmp_path: Path, before: dict[str, bytes]
) -> None:
    kept = tmp_path / "kept.png"
    kept.write_bytes(b"keep")
    assert _preview("99", "one", kept) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "FRAME_NOT_IN_BUNDLE"
    assert kept.read_bytes() == b"keep"
    assert _preview("4", "absence", tmp_path / "case.png") == EXIT_REFUSED
    refusal = last_record(caplog)
    assert refusal["code"] == "CASE_INVALID"
    details = refusal["details"]
    assert isinstance(details, dict)
    assert details["parent_stream_id"] == "one"
    assert _preview("0", "missing", tmp_path / "nope.png") == EXIT_REFUSED
    assert last_record(caplog)["code"] == "BUNDLE_NOT_STAGED"
    assert _preview("4", "one", staged / "one" / "sheet.png") == EXIT_REFUSED
    assert last_record(caplog)["code"] == "STORAGE_FAILED"
    assert not (staged / "one" / "sheet.png").exists()
    assert _snapshot(staged) == before


def _refuse_unwritable_and_missing_case(
    staged: Path, caplog: pytest.LogCaptureFixture, tmp_path: Path, before: dict[str, bytes]
) -> None:
    missing = tmp_path / "missing-dir" / "sheet.png"
    assert _preview("4", "one", missing) == EXIT_REFUSED
    missing_dir = last_record(caplog)
    assert missing_dir["code"] == "STORAGE_FAILED"
    assert "directory does not exist" in str(missing_dir["message"])
    assert not missing.exists()
    staged.chmod(0o755)
    (staged / "dropped").chmod(0o755)
    shutil.rmtree(staged / "dropped")
    assert _preview("4", "one", tmp_path / "partial.png") == EXIT_REFUSED
    assert last_record(caplog)["code"] == "BUNDLE_NOT_STAGED"
    assert not (tmp_path / "partial.png").exists()
    parent = _snapshot(staged)
    assert all(parent[path] == before[path] for path in parent)
    assert any(path.startswith("dropped") for path in before)


def test_refusals_write_nothing_and_a_case_id_names_its_parent(
    staged: Path, cli_root: Path, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    before = _snapshot(staged)
    _refuse_bad_inputs(staged, caplog, tmp_path, before)
    _refuse_unwritable_and_missing_case(staged, caplog, tmp_path, before)


def test_a_stream_with_no_cases_writes_the_parent_alone(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    stage_corpus(CORPUS, data_root)
    root = data_root / "corpus" / CORPUS / "frames"
    out = tmp_path / "parent.png"

    assert _preview("0", "one", out) == EXIT_OK
    preview = last_record(caplog)["preview"]
    assert isinstance(preview, dict)
    assert preview["width"] == WIDTH
    assert [panel["role"] for panel in preview["panels"]] == [ROLE_PARENT]
    _, _, pixels = _png_rgb(out.read_bytes())
    assert pixels == open_frame_bundle(root / "one").read_frame(0)


def test_a_case_that_does_not_match_its_parent_shape_is_refused() -> None:
    parent = _bundle()
    _require_rgb24(parent)
    _require_same_shape(parent, _bundle(stream_id="absence"))
    with pytest.raises(CorpusRefusal) as caught:
        _require_same_shape(parent, _bundle(stream_id="absence", width=WIDTH - 1))
    assert caught.value.code is RefusalCode.CASE_INVALID
    with pytest.raises(CorpusRefusal) as odd:
        _require_rgb24(_bundle(pixel_format="gray"))
    assert odd.value.code is RefusalCode.SOURCE_FORMAT_CHANGED


def test_a_failed_replace_leaves_no_scratch_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(source: str, _destination: str) -> None:
        raise OSError(f"cannot replace {source}")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(CorpusRefusal) as caught:
        _write_bytes(tmp_path / "sheet.png", b"png")
    assert caught.value.code is RefusalCode.STORAGE_FAILED
    assert list(tmp_path.glob(".incoming-*")) == []
