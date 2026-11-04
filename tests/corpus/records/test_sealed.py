"""The read path: a damaged, unsealed or foreign record is refused, and a refusal says why."""

import json
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.read_refusals import NEWER, OLDER, UNSTATED
from ss_track.corpus.records.sealed import read_comparable, read_sealed, read_stated
from tests._sealing import self_sealed

BODY = {"kind": "test-record", "schema_version": 3, "b": [1, None], "a": "value"}
FORMAT = RecordFormat("test-record", 3)


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
