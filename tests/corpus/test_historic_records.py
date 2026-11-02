"""Every kept record, read by today's code: refused by name, and never with a traceback.

A record with only its version number changed proves nothing about a format, so each of these was
written by the code of its own era. See `records/README.md`.
"""

import re
from pathlib import Path

import pytest
import yaml

from ss_track.cli import EXIT_REFUSED, main
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    amend_source_terms,
    build_corpus,
    import_source,
    open_frame_bundle,
)
from ss_track.corpus.builder import CORPUS_MANIFEST
from ss_track.corpus.frame_set import FRAME_SET
from ss_track.corpus.frames import FRAME_BUNDLE
from ss_track.corpus.hash_comparison import HASH_COMPARISON_KIND, HASH_COMPARISON_SCHEMA_VERSION
from ss_track.corpus.host_hashes import STAGED_HASHES, read_staged_hashes
from ss_track.corpus.importer import SOURCE_MANIFEST
from ss_track.corpus.sealed import RecordFormat, read_sealed
from tests.corpus._amending import read_source, rights_with
from tests.corpus._historic import RECORDS, place_record
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    encounter_of,
    group_of,
    last_record,
    reseal,
    stream_of,
)

_CORPUS = "pilot-v1"
_NAME = re.compile(r"(?P<format>[a-z-]+)-schema-(?P<major>\d+)-(?P<commit>[0-9a-f]{7})\.json")
_FORMATS = {
    "bundle": FRAME_BUNDLE,
    "corpus": CORPUS_MANIFEST,
    "frame-set": FRAME_SET,
    "hash-comparison": RecordFormat(HASH_COMPARISON_KIND, HASH_COMPARISON_SCHEMA_VERSION, "none"),
    "source": SOURCE_MANIFEST,
    "staged-hashes": STAGED_HASHES,
}
_RECORDS = sorted(path.name for path in RECORDS.glob("*.json"))
_OLDER_CORPORA = ["corpus-schema-1-294535c.json", "corpus-schema-2-78db68c.json"]
_OLDER_BUNDLES = ["bundle-schema-1-294535c.json", "bundle-schema-2-78db68c.json"]
_OLDER_SOURCES = ["source-schema-1-0238d55.json", "source-schema-1-d6b704d.json"]
_TERMS_MISSING = "corpus-schema-3-d6b704d.json"


def _corpus_path(data_root: Path) -> Path:
    return data_root / "corpus" / _CORPUS / "manifest.json"


def _older(details: dict[str, object], record_format: RecordFormat, major: int) -> None:
    assert details["kind"] == record_format.kind
    assert details["found_schema_version"] == major
    assert details["accepted_schema_versions"] == [record_format.major]
    assert details["age"] == "older"
    assert record_format.older_remedy in str(details["remedy"])


def _major_of(name: str) -> int:
    match = _NAME.fullmatch(name)
    assert match is not None
    return int(match["major"])


def _format_of(name: str) -> RecordFormat:
    match = _NAME.fullmatch(name)
    assert match is not None
    return _FORMATS[match["format"]]


@pytest.mark.parametrize("name", _RECORDS)
def test_a_kept_record_is_intact_named_for_what_it_holds_and_listed(name: str) -> None:
    major = _major_of(name)

    record = read_sealed(RECORDS / name, _format_of(name), older_majors=(major,))

    assert record["schema_version"] == major
    assert name in (RECORDS / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("record_format", _FORMATS.values(), ids=_FORMATS.keys())
def test_every_major_of_every_format_keeps_a_real_record(record_format: RecordFormat) -> None:
    majors = {_major_of(name) for name in _RECORDS if _format_of(name) is record_format}

    assert majors == set(range(1, record_format.major + 1))


@pytest.mark.parametrize("record", _OLDER_CORPORA)
@pytest.mark.parametrize(
    "command",
    [
        ["corpus", "stage", "--corpus", _CORPUS],
        ["corpus", "verify", "--corpus", _CORPUS],
        ["corpus", "hashes", "--corpus", _CORPUS, "--run-id", "kept"],
    ],
    ids=["stage", "verify", "hashes"],
)
def test_an_older_corpus_refuses_each_command_by_name(
    record: str, command: list[str], cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = place_record(record, _corpus_path(cli_root))
    before = path.read_bytes()

    assert main(command) == EXIT_REFUSED

    refusal = last_record(caplog)
    assert refusal["code"] == "RECORD_SCHEMA_UNSUPPORTED"
    details = refusal["details"]
    assert isinstance(details, dict)
    _older(details, CORPUS_MANIFEST, _major_of(record))
    assert details["path"] == str(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("command", ["stage", "verify"])
def test_a_corpus_that_entered_schema_3_without_terms_refuses_by_name(
    command: str, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    place_record(_TERMS_MISSING, _corpus_path(cli_root))

    assert main(["corpus", command, "--corpus", _CORPUS]) == EXIT_REFUSED

    refusal = last_record(caplog)
    assert refusal["code"] == "RECORD_SCHEMA_UNSUPPORTED"
    details = refusal["details"]
    assert isinstance(details, dict)
    assert "--amend-terms" in str(details["remedy"])
    assert details["stream_id"] == "one"
    assert details["source_sha256"]


@pytest.mark.parametrize("record", _OLDER_BUNDLES)
def test_an_older_bundle_refuses_by_name(record: str, tmp_path: Path) -> None:
    place_record(record, tmp_path / "one" / "manifest.json")

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(tmp_path / "one")

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    _older(caught.value.details, FRAME_BUNDLE, _major_of(record))


@pytest.mark.parametrize("record", _OLDER_SOURCES)
def test_an_older_source_refuses_a_build_by_name(
    record: str, media: Path, data_root: Path, write_corpus: WriteCorpus
) -> None:
    sha256 = str(read_source(RECORDS / record)["source"]["sha256"])  # type: ignore[index, call-overload]
    place_record(record, data_root / "import" / sha256 / "manifest.json")
    declared = write_corpus([{"stream_id": "one", "source_sha256": sha256}])

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(declared, data_root)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    _older(caught.value.details, SOURCE_MANIFEST, 1)


def test_records_at_the_current_major_still_open() -> None:
    assert read_staged_hashes(RECORDS / "staged-hashes-schema-1-0bf3b9e.json")
    assert read_sealed(RECORDS / "frame-set-schema-1-fd982a1.json", FRAME_SET)
    assert read_sealed(RECORDS / "source-schema-2-129a350.json", SOURCE_MANIFEST)
    assert read_sealed(RECORDS / "corpus-schema-3-129a350.json", CORPUS_MANIFEST)


def test_a_real_bundle_at_the_current_major_opens(tmp_path: Path) -> None:
    place_record("bundle-schema-3-d6b704d.json", tmp_path / "one" / "manifest.json")

    assert open_frame_bundle(tmp_path / "one").stream_id == "one"


def _import_refused(data_root: Path, declared: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        import_source(declared, data_root)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    return caught.value


def test_a_reimport_over_an_older_source_names_the_amendment_which_then_accepts_it(
    imported: ImportResult,
    write_recording: WriteRecording,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_decode(*_: object) -> None:
        raise AssertionError("a record no import can replace must be refused before a decode")

    path = imported.manifest_path
    path.chmod(0o644)
    place_record("source-schema-1-d6b704d.json", path)
    with monkeypatch.context() as patched:
        patched.setattr("ss_track.corpus.importer.inspect_media", no_decode)
        refusal = _import_refused(data_root, write_recording())

    _older(refusal.details, SOURCE_MANIFEST, 1)
    assert "--amend-terms" in refusal.message
    amended = amend_source_terms(write_recording(rights=rights_with()), data_root)
    assert amended.status == "amended"
    assert read_sealed(path, SOURCE_MANIFEST)["schema_version"] == SOURCE_MANIFEST.major


def test_a_newer_source_is_told_apart_from_an_older_one(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    reseal(imported.manifest_path, schema_version=SOURCE_MANIFEST.major + 1)

    refusal = _import_refused(data_root, write_recording())

    assert refusal.details["age"] == "newer"
    assert "install the ss-track version" in str(refusal.details["remedy"])


def test_the_remedy_of_an_older_corpus_warns_that_no_guard_checks_its_splits() -> None:
    assert "keep every source in the split" in CORPUS_MANIFEST.older_remedy


def test_a_rebuild_over_an_older_corpus_is_refused_for_its_schema(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    place_record(_OLDER_CORPORA[1], _corpus_path(data_root))

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported)]), data_root)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    _older(caught.value.details, CORPUS_MANIFEST, 2)


def test_a_predecessor_manifest_of_another_major_stays_refused_at_build(
    imported: ImportResult, media: Path, data_root: Path
) -> None:
    place_record(_OLDER_CORPORA[1], _corpus_path(data_root))
    group = group_of("site-a", "development", encounter_of("enc", stream_of(imported)))
    declared = media / "next.yaml"
    declared.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "corpus_id": "pilot-v2",
                "supersedes": _CORPUS,
                "scenario_rights": {"sharing": "restricted", "max_sensitivity": "high"},
                "groups": [group],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(declared, data_root)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    _older(caught.value.details, CORPUS_MANIFEST, 2)
