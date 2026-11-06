"""A predecessor's bundles of another major: compared through their projection, else named.

`other_schema` means only that a bundle's major keeps no projection, and it never fails a successor.
"""

from pathlib import Path

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.storage.layout import frame_set_path
from tests.corpus._historic import place_record
from tests.corpus._shared_frames import V1, V2, check_of, named, not_compared, stage_refused
from tests.corpus.conftest import WriteCorpus, reseal, single_group, stream_of

_NO_PROJECTION = 4  # a newer major: this code keeps no projection of it


def _give_unprojected_bundle(data_root: Path, stream_id: str) -> None:
    """Leave one of a predecessor's bundles at a major this code cannot project."""
    bundle = data_root / "corpus" / V1 / "frames" / stream_id
    bundle.chmod(0o755)
    reseal(bundle / "manifest.json", schema_version=_NO_PROJECTION)


def test_a_real_predecessor_of_major_2_is_compared_through_its_projections(
    copy: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    corpus = data_root / "corpus" / V1
    place_record("corpus-schema-2-78db68c.json", corpus / "manifest.json")
    place_record("bundle-schema-2-78db68c.json", corpus / "frames" / "one" / "manifest.json")
    place_record("frame-set-schema-1-fd982a1.json", frame_set_path(data_root, V1))
    v2 = [single_group("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    result = stage_corpus(V2, data_root)

    assert check_of(result)["compared_versions"] == [V1]
    assert not_compared(result) == [(V1, "other_decode_policy", [])]


def test_a_predecessor_holding_an_unprojected_bundle_names_it_and_fails_nothing(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single_group("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    _give_unprojected_bundle(data_root, "seen")
    v2 = [single_group("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    result = stage_corpus(V2, data_root)

    assert result.status == "staged"
    assert check_of(result)["compared_versions"] == []
    assert not_compared(result) == [(V1, "other_schema", ["seen"])]
    assert not_compared(verify_corpus_frames(V2, data_root)) == [(V1, "other_schema", ["seen"])]


def test_a_predecessor_with_one_unprojected_bundle_is_compared_on_the_rest(
    copy: ImportResult,
    original: ImportResult,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [
        single_group("site-a", "development", stream_of(original, stream_id="kept")),
        single_group("site-c", "development", stream_of(third, stream_id="seen")),
    ]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    _give_unprojected_bundle(data_root, "seen")
    v2 = [single_group("site-b", "locked", stream_of(copy, stream_id="held-out"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    refusal = stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert named(refusal, "stream_id") == ["kept", "held-out"]


def test_a_damaged_predecessor_bundle_still_refuses(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single_group("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    manifest = data_root / "corpus" / V1 / "frames" / "seen" / "manifest.json"
    manifest.chmod(0o644)
    manifest.write_text("not a record", encoding="ascii")
    v2 = [single_group("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    stage_refused(V2, data_root, RefusalCode.RECORD_TAMPERED)
