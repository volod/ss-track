"""The fixed corpus two architectures stage: its table, its stored sources and its comparison."""

import json
import shutil
from pathlib import Path

import pytest

from ss_track.corpus import compare_staged_hashes
from ss_track.corpus.host_hashes import STAGED_HASHES_NAME, run_directory
from ss_track.corpus.transforms import TRANSFORM_REVISIONS
from tests.corpus._fixed_corpus import _CASE_PARENT, _CASES, CORPUS_ID, SOURCES, stage_sources
from tests.corpus._fixed_corpus import write_sources as write_fixed_sources

_RUN = "fixed-run"
_INVERSE_DCT_CODECS = {"mjpeg", "mpeg1video", "mpeg2video", "mpeg4", "dvvideo", "dnxhd"}


def _hashes(data_root: Path) -> dict[str, object]:
    path = run_directory(data_root, _RUN) / STAGED_HASHES_NAME
    return json.loads(path.read_text(encoding="ascii"))


@pytest.fixture(scope="module")
def stored(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Every source, written once, which is what the other host receives."""
    return write_fixed_sources(tmp_path_factory.mktemp("fixed") / "sources")


@pytest.fixture(scope="module")
def staged(stored: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    data_root = tmp_path_factory.mktemp("first") / "data"
    stage_sources(stored, _RUN, data_root)
    return data_root


def test_every_source_has_one_name_and_every_transform_runs_once() -> None:
    names = [source.name for source in SOURCES]

    assert len(names) == len(set(names))
    assert _CASE_PARENT in names
    assert {transform for transform, _ in _CASES} == set(TRANSFORM_REVISIONS)


def test_the_table_holds_the_codecs_with_no_normative_inverse_dct() -> None:
    assert {source.codec for source in SOURCES} >= _INVERSE_DCT_CODECS


def test_every_source_stages_under_the_strict_decode(staged: Path) -> None:
    record = _hashes(staged)
    bundles = record["bundles"]

    assert record["corpus_id"] == CORPUS_ID
    assert isinstance(bundles, list)
    assert len(bundles) == len(SOURCES) + len(_CASES)


def test_every_source_decodes_as_the_format_it_claims(staged: Path) -> None:
    """Regression: a container with no tag for P010 read back as RGB555, under the wrong name."""
    record = _hashes(staged)
    bundles, sources = record["bundles"], record["sources"]
    assert isinstance(bundles, list)
    assert isinstance(sources, list)
    source_hashes = {line["stream_id"]: line["source_sha256"] for line in bundles}
    decoded = {line["source_sha256"]: line["source_pixel_format"] for line in sources}

    found = {source.name: decoded[source_hashes[source.name]] for source in SOURCES}

    assert found == {source.name: source.decoded_format for source in SOURCES}


def test_no_two_sources_share_a_frame(staged: Path) -> None:
    """A later refusal of frames repeated inside one group must not trip over this fixture."""
    record = _hashes(staged)
    bundles = record["bundles"]
    assert isinstance(bundles, list)
    streams = [line for line in bundles if line["parent_stream_id"] is None]
    frames = [frame[2] for line in streams for frame in line["frames"]]

    assert len(frames) == len(set(frames))


def test_stored_sources_moved_to_another_root_give_one_frame_set(
    stored: Path, staged: Path, tmp_path: Path
) -> None:
    moved = shutil.copytree(stored, tmp_path / "carried")
    other_root = tmp_path / "other"

    frame_set = stage_sources(moved, _RUN, other_root)
    result = compare_staged_hashes(
        run_directory(staged, _RUN) / STAGED_HASHES_NAME,
        run_directory(other_root, _RUN) / STAGED_HASHES_NAME,
        _RUN,
        other_root,
    )

    assert frame_set == _hashes(staged)["frame_set_sha256"]
    assert result.comparison["status"] == "identical"
    assert result.comparison["bundle_count"] == len(SOURCES) + len(_CASES)
