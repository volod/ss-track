"""Scale reduction uses deterministic area averages, including partial edge blocks."""

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import build_corpus, stage_corpus, verify_corpus_frames
from ss_track.corpus.bundles.bundle_reader import open_frame_bundle
from ss_track.corpus.cases.preview import preview_stream
from ss_track.corpus.cases.transforms import prepare_case
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.sources.importer import ImportResult
from tests.corpus.cases._staged_cases import CORPUS, case_frames_root, stage_cases
from tests.corpus.cases.test_preview_png import _png_rgb
from tests.corpus.conftest import (
    WriteCorpus,
    bundle_identity,
    case_of,
    reseal,
    reseal_bundle,
    stream_of,
)

_HALF = case_of("small", "scale_reduction", 0, {"factor": 2})


def _recipe(factor: int) -> dict[str, Any]:
    return {
        "case_id": "s",
        "transform": "scale_reduction",
        "parameters": {"factor": factor},
        "window": {"start_frame": 0, "end_frame": 1},
        "seed": 0,
    }


@pytest.mark.parametrize(
    ("rows", "factor", "expected"),
    [
        ([[0, 2], [4, 6]], 2, [[3]]),
        ([[0, 2, 8], [4, 6, 10], [12, 14, 16]], 2, [[3, 9], [13, 16]]),
        ([[0, 2, 4, 6], [8, 10, 12, 14]], 3, [[6, 10]]),
    ],
)
def test_area_average(rows: list[list[int]], factor: int, expected: list[list[int]]) -> None:
    pixels = np.repeat(np.array(rows, dtype=np.uint8)[:, :, None], 3, axis=2)
    height, width = pixels.shape[:2]
    result = prepare_case(_recipe(factor), range(1), width, height, lambda _: pixels)
    assert result.paint is not None
    assert result.paint(pixels, 0)[:, :, 0].tolist() == expected
    assert result.label_transform == {"kind": "scale", "factor": factor}


def test_a_factor_beyond_both_dimensions_averages_the_whole_frame() -> None:
    pixels = np.repeat(np.array([[0, 3, 7]], dtype=np.uint8)[:, :, None], 3, axis=2)
    result = prepare_case(_recipe(5), range(1), 3, 1, lambda _: pixels)
    assert result.paint is not None
    assert result.paint(pixels, 0)[:, :, 0].tolist() == [[3]]
    assert result.output_size == (1, 1)


def test_stage_scale(imported: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> None:
    root = stage_cases(imported, write_corpus, data_root, _HALF)
    parent = open_frame_bundle(root / "one")
    case = open_frame_bundle(root / "small")
    assert (case.width, case.height) == ((parent.width + 1) // 2, (parent.height + 1) // 2)
    assert len(case.read_frame(0)) == case.width * case.height * 3


def test_stage_repeat_and_preview(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path, tmp_path: Path
) -> None:
    root = stage_cases(imported, write_corpus, data_root, _HALF)
    before = {p.name: p.read_bytes() for p in (root / "small").iterdir() if p.is_file()}
    stage_corpus(CORPUS, data_root)
    verify_corpus_frames(CORPUS, data_root)
    assert before == {p.name: p.read_bytes() for p in (root / "small").iterdir() if p.is_file()}
    parent, reduced = open_frame_bundle(root / "one"), open_frame_bundle(root / "small")
    out = tmp_path / "preview.png"
    preview_stream(CORPUS, "one", 0, out, data_root)
    width, height, pixels = _png_rgb(out.read_bytes())
    assert (width, height) == (parent.width * 2, parent.height)
    source = reduced.read_frame(0)
    for y in range(reduced.height):
        start = (y * width + parent.width) * 3
        assert (
            pixels[start : start + reduced.width * 3]
            == source[y * reduced.width * 3 : (y + 1) * reduced.width * 3]
        )


def test_preview_refuses_a_reduced_bundle_of_another_size(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path, tmp_path: Path
) -> None:
    root = stage_cases(imported, write_corpus, data_root, _HALF)
    identity = bundle_identity(root / "small")
    reseal_bundle(root / "small", identity | {"width": identity["width"] + 1})
    out = tmp_path / "preview.png"

    with pytest.raises(CorpusRefusal) as caught:
        preview_stream(CORPUS, "one", 0, out, data_root)
    assert caught.value.code is RefusalCode.CASE_INVALID
    assert caught.value.details["case_id"] == "small"
    assert not out.exists()


def test_no_change_and_partial_window_refused() -> None:
    pixels = np.zeros((1, 1, 3), dtype=np.uint8)
    case = _recipe(2)
    with pytest.raises(CorpusRefusal, match="at least 2"):
        prepare_case(_recipe(1), range(1), 2, 2, lambda _: pixels)
    with pytest.raises(CorpusRefusal, match="changes no pixel"):
        prepare_case(case, range(1), 1, 1, lambda _: pixels)
    with pytest.raises(CorpusRefusal, match="whole selection"):
        prepare_case(case, range(2), 2, 2, lambda _: pixels)


def test_scale_inherits_membership_and_rejects_other_revision(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    result = build_corpus(
        write_corpus([stream_of(imported, generated_cases=[_HALF])]),
        data_root,
    )
    manifest = read_sealed(result.manifest_path, CORPUS_MANIFEST)
    parent = manifest["streams"][0]
    case = manifest["generated_cases"][0]
    assert all(case[key] == parent[key] for key in ("encounter_id", "group_id", "split"))
    reseal(result.manifest_path, generated_cases=[case | {"transform_revision": 99}])
    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)
    assert caught.value.code is RefusalCode.TRANSFORM_REVISION_MISMATCH
    assert not case_frames_root(data_root).exists()
