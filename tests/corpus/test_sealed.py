import json
import stat
from pathlib import Path

import pytest

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sealed import (
    NEWER,
    OLDER,
    SEAL_FIELD,
    UNSTATED,
    RecordFormat,
    canonical_json,
    copy_with_sha256,
    read_sealed,
    seal,
    sha256_bytes,
    sha256_file,
    write_sealed,
)

BODY = {"kind": "test-record", "schema_version": 3, "b": [1, None], "a": "value"}
FORMAT = RecordFormat("test-record", 3, "write it again")


def test_canonical_json_ignores_key_order() -> None:
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})


def test_canonical_json_refuses_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="JSON compliant"):
        canonical_json({"value": float("nan")})


def test_seal_covers_every_field() -> None:
    assert seal(BODY)[SEAL_FIELD] != seal(BODY | {"a": "other"})[SEAL_FIELD]


def test_written_record_reads_back_read_only(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "record.json"

    write_sealed(path, seal(BODY))

    assert read_sealed(path, FORMAT) == seal(BODY)
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
        pytest.param(json.dumps(seal(BODY) | {"a": "edited"}), id="edited"),
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
    path.write_text(json.dumps(seal(BODY) | {"kind": "other"}), encoding="ascii")

    with pytest.raises(CorpusRefusal, match="seal") as caught:
        read_sealed(path, FORMAT)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_an_intact_record_of_another_kind_is_refused_by_kind(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_text(json.dumps(seal(BODY | {"kind": "other"})), encoding="ascii")

    with pytest.raises(CorpusRefusal, match="kind") as caught:
        read_sealed(path, FORMAT)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def _refusal_of(tmp_path: Path, schema_version: object) -> CorpusRefusal:
    path = tmp_path / "record.json"
    body = {key: value for key, value in BODY.items() if key != "schema_version"}
    if schema_version is not ...:
        body["schema_version"] = schema_version  # type: ignore[assignment]
    path.write_text(json.dumps(seal(body)), encoding="ascii")
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(path, FORMAT)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    return caught.value


@pytest.mark.parametrize(
    ("schema_version", "age", "remedy"),
    [
        pytest.param(2, OLDER, "write it again", id="older"),
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


def test_a_reader_that_replaces_an_older_major_may_name_it(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_text(json.dumps(seal(BODY | {"schema_version": 2})), encoding="ascii")

    assert read_sealed(path, FORMAT, older_majors=(2,))["schema_version"] == 2
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(path, FORMAT, older_majors=(1,))
    assert caught.value.details["accepted_schema_versions"] == [1, 3]
