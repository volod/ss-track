"""Sealing a record: one validation before its hash, one read-only write, and hashed copies."""

import json
import stat
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.canonical import SEAL_FIELD, canonical_json, sha256_bytes
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import copy_with_sha256, seal, sha256_file, write_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import RecordFormat
from tests._sealing import self_sealed
from tests.corpus._historic import RECORDS

BODY = {"kind": "test-record", "schema_version": 3, "b": [1, None], "a": "value"}
FORMAT = RecordFormat("test-record", 3)
FRAME_SET_RECORD = RECORDS / "frame-set-schema-1-fd982a1.json"


def _frame_set_body() -> dict[str, Any]:
    record: dict[str, Any] = json.loads(FRAME_SET_RECORD.read_text(encoding="ascii"))
    record.pop(SEAL_FIELD)
    return record


def test_canonical_json_ignores_key_order() -> None:
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})


def test_canonical_json_refuses_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="JSON compliant"):
        canonical_json({"value": float("nan")})


def test_seal_covers_every_field() -> None:
    body = _frame_set_body()

    assert seal(body)[SEAL_FIELD] != seal(body | {"corpus_id": "other"})[SEAL_FIELD]


def test_seal_keeps_the_seal_of_a_kept_record() -> None:
    kept = json.loads(FRAME_SET_RECORD.read_text(encoding="ascii"))

    assert seal(_frame_set_body()) == kept


@pytest.mark.parametrize(
    ("change", "message"),
    [
        pytest.param({"corpus_id": "../escape"}, "/corpus_id", id="breaks-its-contract"),
        pytest.param({"unannounced": 1}, "Additional properties", id="unannounced-key"),
        pytest.param({"schema_version": 1.0}, "major 1.0", id="float-major"),
        pytest.param({"schema_version": 9}, "major 9", id="no-frozen-major"),
        pytest.param({"kind": "test-record"}, "no contract states kind", id="unregistered-kind"),
        pytest.param({"bundles": ({"x": 1},)}, "/bundles/0", id="tuple-as-written"),
    ],
)
def test_a_writer_defect_is_refused_before_anything_is_sealed(
    change: dict[str, Any], message: str
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        seal(_frame_set_body() | change)

    assert caught.value.code is RefusalCode.RECORD_INVALID
    assert message in caught.value.message


def test_a_number_no_json_holds_is_refused_before_a_seal_is_computed() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        seal(_frame_set_body() | {"corpus_id": float("nan")})

    assert caught.value.code is RefusalCode.RECORD_INVALID
    assert "not JSON" in caught.value.message


def test_a_contract_refusal_names_its_version_and_every_violation() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        seal(_frame_set_body() | {"corpus_id": "UPPER", "unannounced": 1})

    details = caught.value.details
    assert details["urn"] == "urn:ss-track:contract:record:frame-set:1.0.0"
    assert [item["pointer"] for item in details["violations"]] == ["", "/corpus_id"]


def test_written_record_reads_back_read_only(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "record.json"

    write_sealed(path, self_sealed(BODY))

    assert read_sealed(path, FORMAT) == self_sealed(BODY)
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    assert [item.name for item in path.parent.iterdir()] == ["record.json"]


def test_copy_hashes_the_copied_bytes(tmp_path: Path) -> None:
    source = tmp_path / "a"
    source.write_bytes(b"payload")

    digest, size = copy_with_sha256(source, tmp_path / "b")

    assert (digest, size) == (sha256_bytes(b"payload"), 7)
    assert sha256_file(tmp_path / "b") == digest


def test_copy_never_overwrites(tmp_path: Path) -> None:
    (tmp_path / "a").write_bytes(b"x")
    (tmp_path / "b").write_bytes(b"y")

    with pytest.raises(FileExistsError):
        copy_with_sha256(tmp_path / "a", tmp_path / "b")
