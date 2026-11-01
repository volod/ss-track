import json
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus
from ss_track.corpus.builder import load_corpus_manifest
from ss_track.corpus.decode import current_decode_policy
from ss_track.corpus.importer import decode_policy_sha256
from ss_track.corpus.sealed import read_sealed
from tests.corpus._media import FRAME_COUNT
from tests.corpus.conftest import WriteCorpus, reseal, stream_of

CORPUS_KIND = "ss-track.corpus-manifest"


def _refused(declaration: Path, data_root: Path, code: RefusalCode) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(declaration, data_root)
    assert caught.value.code is code
    assert not (data_root / "corpus").exists()
    return caught.value


def test_build_binds_each_sequence_to_its_verified_source(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    window = {"start_frame": 2, "end_frame": FRAME_COUNT}

    result = build_corpus(write_corpus([stream_of(imported, selection=window)]), data_root)

    manifest = read_sealed(result.manifest_path, CORPUS_KIND)
    assert result.status == "built"
    assert result.manifest_path == data_root / "corpus" / "pilot-v1" / "manifest.json"
    assert manifest["decode_policy"] == current_decode_policy().as_record()
    assert manifest["streams"] == [
        {
            "stream_id": "one",
            "modality": "camera",
            "encounter_id": "enc-one",
            "group_id": "group-one",
            "split": "development",
            "source_sha256": imported.source_sha256,
            "source_manifest_sha256": imported.manifest_sha256,
            "selection": window,
            "frame_count": FRAME_COUNT,
            "timestamp_quality": "derived",
            "completeness_checks": ["matroska_segment_size"],
            "rights": {
                "holder": "Project Contributors",
                "basis": "owned",
                "retention": "project duration",
                "sharing": "restricted",
            },
            "sensitivity": {"level": "low", "notes": None},
        }
    ]


def test_absent_selection_means_the_whole_sequence(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    result = build_corpus(write_corpus([stream_of(imported)]), data_root)

    streams = read_sealed(result.manifest_path, CORPUS_KIND)["streams"]
    assert isinstance(streams, list) and isinstance(streams[0], dict)
    assert streams[0]["selection"] == {"start_frame": 0, "end_frame": FRAME_COUNT}


@pytest.mark.parametrize(
    "window",
    [
        pytest.param({"start_frame": 0, "end_frame": FRAME_COUNT + 1}, id="one-past-end"),
        pytest.param({"start_frame": FRAME_COUNT, "end_frame": FRAME_COUNT + 5}, id="wholly-past"),
    ],
)
def test_selection_past_the_end_is_refused(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    window: dict[str, int],
) -> None:
    declaration = write_corpus([stream_of(imported, selection=window)])

    refusal = _refused(declaration, data_root, RefusalCode.SELECTION_OUT_OF_RANGE)

    assert refusal.details["frame_count"] == FRAME_COUNT


def test_source_never_imported_is_refused(write_corpus: WriteCorpus, data_root: Path) -> None:
    declaration = write_corpus([{"stream_id": "one", "source_sha256": "c" * 64}])

    _refused(declaration, data_root, RefusalCode.SOURCE_NOT_IMPORTED)


def test_changed_stored_bytes_are_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    stored = imported.manifest_path.parent / "source.mkv"
    stored.chmod(0o644)
    stored.write_bytes(stored.read_bytes() + b"\x00")

    _refused(write_corpus([stream_of(imported)]), data_root, RefusalCode.SOURCE_HASH_MISMATCH)


def test_deleted_stored_source_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    (imported.manifest_path.parent / "source.mkv").unlink()

    _refused(write_corpus([stream_of(imported)]), data_root, RefusalCode.SOURCE_HASH_MISMATCH)


def test_edited_source_manifest_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    path = imported.manifest_path
    record = json.loads(path.read_text(encoding="ascii"))
    record["rights"]["sharing"] = "public"
    path.chmod(0o644)
    path.write_text(json.dumps(record), encoding="ascii")

    _refused(write_corpus([stream_of(imported)]), data_root, RefusalCode.RECORD_TAMPERED)


def test_source_from_another_decoder_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    reseal(imported.manifest_path, decode_policy_sha256="d" * 64)

    _refused(write_corpus([stream_of(imported)]), data_root, RefusalCode.DECODE_POLICY_MISMATCH)


def test_declared_policy_pin_must_match_the_installed_decoder(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    declaration = write_corpus([stream_of(imported)], decode_policy_sha256="e" * 64)

    _refused(declaration, data_root, RefusalCode.DECODE_POLICY_MISMATCH)


def test_matching_policy_pin_is_accepted(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    pin = decode_policy_sha256(current_decode_policy().as_record())

    result = build_corpus(write_corpus([stream_of(imported)], decode_policy_sha256=pin), data_root)

    assert result.status == "built"


def test_repeating_a_build_changes_nothing(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    declaration = write_corpus([stream_of(imported)])

    first = build_corpus(declaration, data_root)
    second = build_corpus(declaration, data_root)

    assert (first.status, second.status) == ("built", "unchanged")
    assert first.manifest_sha256 == second.manifest_sha256


def test_declaration_order_does_not_change_the_corpus_hash(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    one = stream_of(imported, stream_id="one", selection={"start_frame": 0, "end_frame": 4})
    two = stream_of(imported, stream_id="two", selection={"start_frame": 4, "end_frame": 8})

    first = build_corpus(write_corpus([one, two]), data_root)
    second = build_corpus(write_corpus([two, one]), data_root)

    assert second.manifest_sha256 == first.manifest_sha256


def test_a_corpus_from_another_schema_is_refused_by_name(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    result = build_corpus(write_corpus([stream_of(imported)]), data_root)
    reseal(result.manifest_path, schema_version=1)

    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_manifest("pilot-v1", data_root)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert caught.value.details == {
        "record": "manifest.json",
        "found_schema_version": 1,
        "schema_version": 2,
    }


def test_a_corpus_version_cannot_be_redefined(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    window = {"start_frame": 0, "end_frame": 4}
    first = build_corpus(write_corpus([stream_of(imported)]), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported, selection=window)]), data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert caught.value.details["existing_manifest_sha256"] == first.manifest_sha256
