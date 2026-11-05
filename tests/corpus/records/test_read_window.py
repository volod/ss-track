"""Older records under a later major: a view serves as evidence, a `facts` major does not.

Records here are written by today's code at today's major, and a synthetic next major frozen by the
real freeze makes them the older one. Nothing is resealed and no byte moves.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from ss_track.core.refusal import JsonValue
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.records import read_window
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.read_window import View, check_view, view_findings
from ss_track.corpus.records.sealed import read_stated
from ss_track.corpus.versions.builder import CORPUS_MANIFEST, load_corpus_manifest
from tests.corpus._historic import kept_record
from tests.corpus.conftest import (
    WriteCorpus,
    encounter_of,
    group_of,
    place_of,
    reseal,
    stream_of,
)
from tests.corpus.records._next_major import (
    CURRENT,
    NEXT,
    freeze_next,
    installed,
    private_contracts,
    read_as_next,
)

_V1, _V2 = "pilot-v1", "pilot-v2"
_COUNT = {"type": "integer", "minimum": 1, "x-unit": "1", "description": "Number of streams."}
_REVIEW = {"type": "string", "minLength": 1, "description": "Who reviewed the placements."}


def _with_count(record: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    streams = record["streams"]
    assert isinstance(streams, list)
    return dict(record) | {"stream_count": len(streams)}


def _files(root: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _one_group(imported: ImportResult, split: str, group: str = "site-a") -> list[object]:
    return [group_of(group, split, encounter_of("enc", stream_of(imported)))]


@pytest.fixture
def staged(imported: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path) -> str:
    """Stage a version at today's major, then return the seal of its frame set."""
    build_corpus(
        write_grouped_corpus(_one_group(imported, "development"), corpus_id=_V1), data_root
    )
    return stage_corpus(_V1, data_root).frame_set_sha256


@pytest.fixture
def view_major(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    root = private_contracts(tmp_path)
    freeze_next(root, "view", "stream_count", _COUNT)
    read_as_next(monkeypatch, _with_count, derived=["/stream_count"])
    with installed(root):
        yield


@pytest.fixture
def facts_major(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    root = private_contracts(tmp_path)
    freeze_next(root, "facts", "placement_review", _REVIEW)
    read_as_next(monkeypatch)
    with installed(root):
        yield


def test_a_view_major_verifies_with_its_frame_set_and_bytes_unchanged(
    staged: str, data_root: Path, request: pytest.FixtureRequest
) -> None:
    before = _files(data_root / "corpus")
    request.getfixturevalue("view_major")

    verified = verify_corpus_frames(_V1, data_root)
    viewed = load_corpus_manifest(_V1, data_root)

    assert verified.frame_set_sha256 == staged
    assert _files(data_root / "corpus") == before
    assert viewed["schema_version"] == NEXT and viewed["stream_count"] == 1
    written = before[data_root / "corpus" / _V1 / "manifest.json"]
    assert str(viewed["manifest_sha256"]).encode() in written


def test_a_decode_policy_mismatch_still_refuses_through_a_view(
    staged: str, data_root: Path, request: pytest.FixtureRequest
) -> None:
    reseal(data_root / "corpus" / _V1 / "manifest.json", decode_policy_sha256="d" * 64)
    request.getfixturevalue("view_major")

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(_V1, data_root)

    assert caught.value.code is RefusalCode.DECODE_POLICY_MISMATCH


def test_a_facts_major_is_refused_as_evidence_and_stays_inspectable(
    staged: str, data_root: Path, request: pytest.FixtureRequest
) -> None:
    path = data_root / "corpus" / _V1 / "manifest.json"
    before = path.read_bytes()
    request.getfixturevalue("facts_major")

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(_V1, data_root)
    stated = read_stated(path, RecordFormat(CORPUS_MANIFEST.kind, NEXT))

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert caught.value.details | {"path": None} == caught.value.details | {
        "path": None,
        "found_schema_version": CURRENT,
        "accepted_schema_versions": [NEXT],
        "age": "older",
        "disposition": "facts",
        "remedy": "Read it through its disposition.",
    }
    assert stated.disposition == "facts" and stated.record["schema_version"] == CURRENT
    assert path.read_bytes() == before


def test_a_move_from_a_facts_major_is_split_leakage_and_not_a_schema_refusal(
    staged: str,
    imported: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    request: pytest.FixtureRequest,
) -> None:
    request.getfixturevalue("facts_major")
    moved = write_grouped_corpus(
        _one_group(imported, "locked", "held-out"), corpus_id=_V2, supersedes=_V1
    )

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(moved, data_root)

    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    assert caught.value.details["moved_sources"] == [
        {
            "source_sha256": imported.source_sha256,
            "from": place_of(_V1, "site-a", "development"),
            "to": place_of(_V2, "held-out", "locked"),
        }
    ]


def test_a_real_corpus_without_source_terms_is_facts_and_still_guards_its_groups(
    imported: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    path = data_root / "corpus" / _V1 / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(kept_record("corpus-schema-3-d6b704d.json"))
    moved = write_grouped_corpus(_one_group(imported, "locked"), corpus_id=_V2, supersedes=_V1)

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(moved, data_root)

    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    assert caught.value.details["moved_groups"] == [
        {"from": place_of(_V1, "site-a", "development"), "to": place_of(_V2, "site-a", "locked")}
    ]
    assert read_stated(path, CORPUS_MANIFEST).disposition == "facts"


def test_a_view_that_derives_a_rights_field_is_refused(
    staged: str, data_root: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    def invents(record: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        streams = [dict(stream) for stream in record["streams"]]  # type: ignore[union-attr]
        for stream in streams:
            stream["rights"] = dict(stream["rights"]) | {"retain_until": "2099-01-01"}  # type: ignore[call-overload]
        return _with_count(record) | {"streams": streams}  # type: ignore[dict-item]

    request.getfixturevalue("view_major")
    kind = CORPUS_MANIFEST.kind
    declared = View(kind, CURRENT, ("/stream_count", "/streams/*/rights/retain_until"), invents)
    undeclared = View(kind, CURRENT, ("/stream_count",), invents)
    monkeypatch.setitem(read_window.INSTALLED_VIEWS, (kind, CURRENT), declared)

    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_manifest(_V1, data_root)

    assert caught.value.code is RefusalCode.CONTRACT_SET_INVALID
    assert "a view never derives retain_until, rights" in caught.value.message
    assert view_findings(undeclared) == []
    record = read_stated(data_root / "corpus" / _V1 / "manifest.json", CORPUS_MANIFEST).record
    assert any("rights" in finding for finding in check_view(undeclared, record))


def test_a_view_never_serves_a_shape_that_lacks_source_terms(
    data_root: Path, request: pytest.FixtureRequest
) -> None:
    path = data_root / "corpus" / _V1 / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(kept_record("corpus-schema-3-d6b704d.json"))
    request.getfixturevalue("view_major")

    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_manifest(_V1, data_root)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert caught.value.details["shape"] == "corpus-3-without-source-terms"
    assert caught.value.details["disposition"] == "facts"
    assert caught.value.details["accepted_schema_versions"] == [CURRENT, NEXT]
