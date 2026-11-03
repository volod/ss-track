import json
import stat
from pathlib import Path
from typing import Any

import pytest

from ss_track.canonical import SEAL_FIELD, canonical_json, sha256_bytes
from ss_track.corpus.sealed import (
    NEWER,
    OLDER,
    UNSTATED,
    RecordFormat,
    copy_with_sha256,
    read_comparable,
    read_sealed,
    read_stated,
    seal,
    sha256_file,
    write_sealed,
)
from ss_track.refusal import CorpusRefusal, RefusalCode
from tests._sealing import self_sealed

BODY = {"kind": "test-record", "schema_version": 3, "b": [1, None], "a": "value"}
FORMAT = RecordFormat("test-record", 3)
FRAME_SET_RECORD = Path(__file__).parent / "records" / "frame-set-schema-1-fd982a1.json"


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


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("not json", id="not-json"),
        pytest.param("[1]", id="not-an-object"),
        pytest.param(json.dumps({"kind": "other"}), id="wrong-kind"),
        pytest.param(json.dumps(self_sealed(BODY) | {"a": "edited"}), id="edited"),
        pytest.param(json.dumps(BODY), id="unsealed"),
        pytest.param('{"kind": "test-record", "a": NaN}', id="not-a-number"),
        pytest.param('{"a": Infinity}', id="infinite"),
        pytest.param('{"a": ' + "9" * 5000 + "}", id="integer-too-long"),
        pytest.param("[" * 200_000, id="nested-too-deep"),
    ],
)
def test_damaged_records_are_refused(tmp_path: Path, content: str) -> None:
    path = tmp_path / "record.json"
    path.write_text(content, encoding="ascii")

    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(path, FORMAT)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_missing_record_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(tmp_path / "absent.json", FORMAT)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_the_seal_is_checked_before_anything_it_covers_is_believed(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_text(json.dumps(self_sealed(BODY) | {"kind": "other"}), encoding="ascii")

    with pytest.raises(CorpusRefusal, match="seal") as caught:
        read_sealed(path, FORMAT)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_an_intact_record_of_another_kind_is_refused_by_kind(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_text(json.dumps(self_sealed(BODY | {"kind": "other"})), encoding="ascii")

    with pytest.raises(CorpusRefusal, match="kind") as caught:
        read_sealed(path, FORMAT)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def _refusal_of(tmp_path: Path, schema_version: object) -> CorpusRefusal:
    path = tmp_path / "record.json"
    body = {key: value for key, value in BODY.items() if key != "schema_version"}
    if schema_version is not ...:
        body["schema_version"] = schema_version  # type: ignore[assignment]
    path.write_text(json.dumps(self_sealed(body)), encoding="ascii")
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(path, FORMAT)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    return caught.value


@pytest.mark.parametrize(
    ("schema_version", "age", "remedy"),
    [
        pytest.param(2, OLDER, "trusted copy", id="older-with-no-change-log"),
        pytest.param(4, NEWER, "install the ss-track version", id="newer"),
        pytest.param(..., UNSTATED, "trusted copy", id="absent"),
        pytest.param(None, UNSTATED, "trusted copy", id="null"),
        pytest.param("3", UNSTATED, "trusted copy", id="text"),
        pytest.param(3.0, UNSTATED, "trusted copy", id="float-equal-to-the-major"),
        pytest.param(True, UNSTATED, "trusted copy", id="bool-equal-to-one"),
    ],
)
def test_a_refusal_states_the_record_its_major_its_age_and_the_remedy(
    tmp_path: Path, schema_version: object, age: str, remedy: str
) -> None:
    refusal = _refusal_of(tmp_path, schema_version)

    details = refusal.details
    assert details["record"] == "record.json"
    assert details["path"] == str(tmp_path / "record.json")
    assert details["kind"] == "test-record"
    assert details["found_schema_version"] == (None if schema_version is ... else schema_version)
    assert details["accepted_schema_versions"] == [3]
    assert details["age"] == age
    assert remedy in str(details["remedy"])
    assert remedy in refusal.message


def test_an_older_record_no_change_log_states_is_neither_stated_nor_projected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "record.json"
    path.write_text(json.dumps(self_sealed(BODY | {"schema_version": 2})), encoding="ascii")

    with pytest.raises(CorpusRefusal) as caught:
        read_stated(path, FORMAT)
    assert caught.value.details["disposition"] is None
    assert caught.value.details["accepted_schema_versions"] == [3]
    found = read_comparable(path, FORMAT)
    assert (found.major, found.projected) == (2, None)
    assert found.seal == json.loads(path.read_text(encoding="ascii"))["manifest_sha256"]
