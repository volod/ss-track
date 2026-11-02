"""A predecessor holding a bundle of another major: named and never a failure of its successor."""

from pathlib import Path

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus._historic import kept_record
from tests.corpus._shared_frames import (
    V1,
    V2,
    check_of,
    named,
    not_compared,
    single,
    stage_refused,
)
from tests.corpus.conftest import WriteCorpus, stream_of


def _give_older_bundle(data_root: Path, stream_id: str) -> None:
    """Leave one of a predecessor's bundles as the real record of an earlier major."""
    bundle = data_root / "corpus" / V1 / "frames" / stream_id
    bundle.chmod(0o755)
    manifest = bundle / "manifest.json"
    manifest.chmod(0o644)
    manifest.write_bytes(kept_record("bundle-schema-2-78db68c.json"))


def test_a_predecessor_holding_another_majors_bundle_is_named_and_fails_nothing(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    _give_older_bundle(data_root, "seen")
    v2 = [single("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    result = stage_corpus(V2, data_root)

    assert result.status == "staged"
    assert check_of(result)["compared_versions"] == []
    assert not_compared(result) == [(V1, "other_schema", ["seen"])]
    assert not_compared(verify_corpus_frames(V2, data_root)) == [(V1, "other_schema", ["seen"])]


def test_a_predecessor_with_one_bundle_of_another_major_is_compared_on_the_rest(
    copy: ImportResult,
    original: ImportResult,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [
        single("site-a", "development", stream_of(original, stream_id="kept")),
        single("site-c", "development", stream_of(third, stream_id="seen")),
    ]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    _give_older_bundle(data_root, "seen")
    v2 = [single("site-b", "locked", stream_of(copy, stream_id="held-out"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    refusal = stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert named(refusal, "stream_id") == ["kept", "held-out"]


def test_a_damaged_predecessor_bundle_still_refuses(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    manifest = data_root / "corpus" / V1 / "frames" / "seen" / "manifest.json"
    manifest.chmod(0o644)
    manifest.write_text("not a record", encoding="ascii")
    v2 = [single("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    stage_refused(V2, data_root, RefusalCode.RECORD_TAMPERED)
