"""`ss-track contracts validate`: what an operator sees for a good, a damaged and an unknown file."""

from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import RefusalCode
from ss_track.schema import validate_file
from ss_track.schema.validation.strict import VIOLATION_LIMIT
from tests.schema.conftest import (
    KEPT_FRAME_SET,
    Register,
    versioned_schema,
)
from tests.schema.validation._command_files import (
    FRAME_SET_CONTRACT,
    FRAME_SET_URN,
    kept_record,
    refused_validation,
    resealed,
    write_json,
)

_HASH = "a" * 64


def test_the_kept_frame_set_validates_with_no_byte_changed() -> None:
    before = KEPT_FRAME_SET.read_bytes()

    result = validate_file(KEPT_FRAME_SET)

    assert KEPT_FRAME_SET.read_bytes() == before
    assert result.to_record() == {
        "status": "valid",
        "path": str(KEPT_FRAME_SET),
        "contract": FRAME_SET_CONTRACT,
        "version": "1.0.0",
        "urn": FRAME_SET_URN,
        "seal_checked": True,
    }


def test_a_generated_case_line_validates(tmp_path: Path) -> None:
    record = kept_record()
    parent = record["bundles"][0]
    case = parent | {"stream_id": "shaken", "parent_stream_id": parent["stream_id"]}
    record["bundles"] = [parent, case]

    assert validate_file(write_json(tmp_path, resealed(record))).contract == FRAME_SET_CONTRACT


def _extra_key(record: dict[str, Any]) -> None:
    record["surprise"] = 1


def _extra_nested_key(record: dict[str, Any]) -> None:
    record["bundles"][0]["surprise"] = 1


def _missing_key(record: dict[str, Any]) -> None:
    del record["corpus_id"]


def _missing_nested_key(record: dict[str, Any]) -> None:
    del record["bundles"][0]["source_sha256"]


def _short_hash(record: dict[str, Any]) -> None:
    record["corpus_manifest_sha256"] = "abc"


def _uppercase_hash(record: dict[str, Any]) -> None:
    record["bundles"][0]["bundle_sha256"] = "A" * 64


def _hash_with_a_newline(record: dict[str, Any]) -> None:
    record["bundles"][0]["bundle_sha256"] = _HASH + "\n"


def _no_bundles(record: dict[str, Any]) -> None:
    record["bundles"] = []


def _bad_identifier(record: dict[str, Any]) -> None:
    record["bundles"][0]["stream_id"] = "Not An Id"


def _bad_parent(record: dict[str, Any]) -> None:
    record["bundles"][0]["parent_stream_id"] = "Not An Id"


def _float_major(record: dict[str, Any]) -> None:
    record["schema_version"] = 1.0


def _true_major(record: dict[str, Any]) -> None:
    record["schema_version"] = True


def _other_major(record: dict[str, Any]) -> None:
    record["schema_version"] = 2


@pytest.mark.parametrize(
    ("alter", "pointer"),
    [
        (_extra_key, ""),
        (_extra_nested_key, "/bundles/0"),
        (_missing_key, ""),
        (_missing_nested_key, "/bundles/0"),
        (_short_hash, "/corpus_manifest_sha256"),
        (_uppercase_hash, "/bundles/0/bundle_sha256"),
        (_hash_with_a_newline, "/bundles/0/bundle_sha256"),
        (_no_bundles, "/bundles"),
        (_bad_identifier, "/bundles/0/stream_id"),
        (_bad_parent, "/bundles/0/parent_stream_id"),
        (_float_major, "/schema_version"),
        (_true_major, "/schema_version"),
        (_other_major, "/schema_version"),
    ],
)
def test_an_altered_copy_is_refused_by_name(tmp_path: Path, alter: Any, pointer: str) -> None:
    record = kept_record()
    alter(record)

    refusal = refused_validation(write_json(tmp_path, resealed(record)))

    assert refusal.code is RefusalCode.RECORD_INVALID
    assert refusal.details["urn"] == FRAME_SET_URN
    violations = refusal.details["violations"]
    assert isinstance(violations, list)
    assert pointer in [item["pointer"] for item in violations]  # type: ignore[index, call-overload]
    assert refusal.details["limit"] == VIOLATION_LIMIT


def test_a_record_whose_content_moved_is_tampered_though_its_shape_is_fine(tmp_path: Path) -> None:
    record = kept_record()
    record["corpus_manifest_sha256"] = _HASH

    refusal = refused_validation(write_json(tmp_path, record))

    assert refusal.code is RefusalCode.RECORD_TAMPERED
    assert refusal.details == {"record": "record.json"}


def test_a_family_with_no_seal_is_not_held_to_one(
    contract_root: Path, register: Register, tmp_path: Path
) -> None:
    register(versioned_schema("declaration", "plain", "1.0.0"))
    path = write_json(tmp_path, {"schema_version": 1, "name": "x"})

    result = validate_file(path, contract_name="declaration/plain", root=contract_root)

    assert not result.seal_checked


def test_a_declaration_that_breaks_its_contract_is_manifest_invalid(
    contract_root: Path, register: Register, tmp_path: Path
) -> None:
    register(versioned_schema("declaration", "plain", "1.0.0"))
    path = write_json(tmp_path, {"schema_version": 1, "surprise": True})

    refusal = refused_validation(path, contract_name="declaration/plain", root=contract_root)

    assert refusal.code is RefusalCode.MANIFEST_INVALID


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("{", "Expecting"),
        ('{"a": NaN}', "NaN is not JSON"),
        ('{"a": Infinity}', "Infinity is not JSON"),
        ('{"a": -Infinity}', "-Infinity is not JSON"),
        ('{"a": 1, "a": 2}', "a key is repeated"),
        ('{"b": {"a": 1, "a": 2}}', "a key is repeated"),
        ("[" * 200000, ""),
        ("1" * 5000, "integer"),
    ],
)
def test_a_file_that_is_not_strict_json_is_refused_with_no_traceback(
    tmp_path: Path, text: str, reason: str
) -> None:
    path = tmp_path / "broken.json"
    path.write_text(text, encoding="ascii")

    refusal = refused_validation(path)

    assert refusal.code is RefusalCode.RECORD_INVALID
    assert reason in refusal.message


def test_a_file_that_is_not_text_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\xfa")

    assert refused_validation(path).code is RefusalCode.RECORD_INVALID


@pytest.mark.parametrize("document", [{"name": "x"}, [1, 2], "text", 3, None])
def test_a_file_that_does_not_name_its_format_must_be_given_one(
    tmp_path: Path, document: object
) -> None:
    refusal = refused_validation(write_json(tmp_path, document))

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert "--contract" in refusal.message


def test_a_kind_with_no_contract_is_named(tmp_path: Path) -> None:
    refusal = refused_validation(
        write_json(tmp_path, {"kind": "ss-track.unknown", "schema_version": 1})
    )

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert refusal.details == {"kind": "ss-track.unknown"}


def test_the_contract_of_another_format_refuses_the_file() -> None:
    other = KEPT_FRAME_SET.with_name("corpus-schema-3-129a350.json")

    assert (
        refused_validation(other, contract_name=FRAME_SET_CONTRACT).code
        is RefusalCode.RECORD_INVALID
    )


def test_shared_types_state_no_document_so_they_accept_none() -> None:
    refusal = refused_validation(KEPT_FRAME_SET, contract_name="shared/types")

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert refusal.details == {"contract": "shared/types"}
