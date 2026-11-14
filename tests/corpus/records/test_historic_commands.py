"""Every kept record, met by today's commands: refused by name, and never with a traceback.

A record with only its version number changed proves nothing about a format, so each of these was
written by the code of its own era. See `kept_records/README.md`.
"""

from pathlib import Path
from unittest.mock import ANY

import pytest
import yaml

from ss_track.cli import main
from ss_track.commands.report import EXIT_REFUSED
from ss_track.core.evidence.sealed import read_comparable, read_sealed
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    amend_source_terms,
    build_corpus,
    import_source,
    open_frame_bundle,
)
from ss_track.corpus.records.kinds import (
    CORPUS_MANIFEST,
    FRAME_BUNDLE,
    SOURCE_MANIFEST,
    RecordFormat,
)
from ss_track.schema.validation.enforce import older_remedy
from tests.corpus._amending import read_source, rights_with
from tests.corpus._historic import RECORDS, major_of, place_record
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
_OLDER_CORPORA = ["corpus-schema-1-294535c.json", "corpus-schema-2-78db68c.json"]
_OLDER_BUNDLES = ["bundle-schema-1-294535c.json", "bundle-schema-2-78db68c.json"]
_OLDER_SOURCES = [
    "source-schema-1-0238d55.json",
    "source-schema-1-d6b704d.json",
    "source-schema-2-129a350.json",
]
_TERMS_MISSING = "corpus-schema-3-d6b704d.json"


def _corpus_path(data_root: Path) -> Path:
    return data_root / "corpus" / _CORPUS / "manifest.json"


def _older(details: dict[str, object], record_format: RecordFormat, major: int) -> None:
    assert details["kind"] == record_format.kind
    assert details["found_schema_version"] == major
    assert details["accepted_schema_versions"] == [record_format.major]
    assert details["age"] == "older"
    migration = older_remedy(record_format.kind, major)
    assert migration is not None and details["remedy"] == migration


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
    _older(details, CORPUS_MANIFEST, major_of(record))
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
    assert details["shape"] == "corpus-3-without-source-terms"
    assert details["disposition"] == "facts"
    assert details["lacking"] == ["one"]


@pytest.mark.parametrize("record", _OLDER_BUNDLES)
def test_an_older_bundle_refuses_by_name(record: str, tmp_path: Path) -> None:
    place_record(record, tmp_path / "one" / "manifest.json")

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(tmp_path / "one")

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    _older(caught.value.details, FRAME_BUNDLE, major_of(record))


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
    _older(caught.value.details, SOURCE_MANIFEST, major_of(record))


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
        patched.setattr("ss_track.corpus.sources.importer.inspect_media", no_decode)
        refusal = _import_refused(data_root, write_recording())

    _older(refusal.details, SOURCE_MANIFEST, 1)
    assert "--amend-terms" in refusal.message
    amended = amend_source_terms(
        write_recording(rights=rights_with()), data_root, amend_capture=True
    )
    assert amended.status == "amended"
    assert read_sealed(path, SOURCE_MANIFEST)["schema_version"] == SOURCE_MANIFEST.major


def test_a_newer_source_is_told_apart_from_an_older_one(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    reseal(imported.manifest_path, schema_version=SOURCE_MANIFEST.major + 1)

    refusal = _import_refused(data_root, write_recording())

    assert refusal.details["age"] == "newer"
    assert "install the ss-track version" in str(refusal.details["remedy"])


def test_a_rebuild_over_an_older_corpus_is_refused_for_its_schema(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    place_record(_OLDER_CORPORA[1], _corpus_path(data_root))

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported)]), data_root)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    _older(caught.value.details, CORPUS_MANIFEST, 2)


def _successor(media: Path, imported: ImportResult, split: str = "development") -> Path:
    group = group_of("site-a", split, encounter_of("enc", stream_of(imported)))
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
    return declared


def test_a_predecessor_of_major_2_is_compared_through_its_projection(
    imported: ImportResult, media: Path, data_root: Path
) -> None:
    kept = place_record(_OLDER_CORPORA[1], _corpus_path(data_root))

    built = build_corpus(_successor(media, imported), data_root)

    lineage = built.to_record()["lineage"]
    assert isinstance(lineage, dict)
    assert lineage["compared_versions"] == [_CORPUS]
    assert "not_compared" not in lineage
    assert lineage["supersedes_manifest_sha256"] == read_comparable(kept, CORPUS_MANIFEST).seal
    assert lineage["removed"] == [
        {"source_sha256": ANY, "group_id": "site-a", "split": "development"}
    ]


def test_a_predecessor_of_major_1_holds_no_split_and_is_not_compared(
    imported: ImportResult, media: Path, data_root: Path
) -> None:
    place_record(_OLDER_CORPORA[0], _corpus_path(data_root))

    lineage = build_corpus(_successor(media, imported, "locked"), data_root).to_record()["lineage"]

    assert lineage == lineage | {
        "status": "linked",
        "compared_versions": [],
        "not_compared": [{"corpus_id": _CORPUS, "reason": "other_schema", "stream_ids": []}],
        "added": [],
    }
