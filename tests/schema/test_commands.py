"""`ss-track contracts`: what an operator sees for a good, a damaged and an unknown file."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import EXIT_OK, EXIT_REFUSED, build_parser, main
from ss_track.corpus.sealed import seal
from ss_track.refusal import CorpusRefusal, RefusalCode
from ss_track.schema import list_contracts, validate_file
from ss_track.schema.strict import VIOLATION_LIMIT
from tests.schema.conftest import (
    KEPT_FRAME_SET,
    Register,
    frame_set_path,
    read_registry,
    version_entry,
    versioned_schema,
    write_registry,
)

_FRAME_SET = "record/frame-set"
_URN = "urn:ss-track:contract:record:frame-set:1.0.0"
_HASH = "a" * 64


def _kept() -> dict[str, Any]:
    record: dict[str, Any] = json.loads(KEPT_FRAME_SET.read_text(encoding="ascii"))
    return record


def _write(tmp_path: Path, record: object, name: str = "record.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(record), encoding="ascii")
    return path


def _resealed(record: dict[str, Any]) -> dict[str, Any]:
    """Return a record consistent with itself, so only its structure can refuse it."""
    return seal({key: value for key, value in record.items() if key != "manifest_sha256"})


def _refused(path: Path, **options: Any) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        validate_file(path, **options)
    return caught.value


def test_the_kept_frame_set_validates_with_no_byte_changed() -> None:
    before = KEPT_FRAME_SET.read_bytes()

    result = validate_file(KEPT_FRAME_SET)

    assert KEPT_FRAME_SET.read_bytes() == before
    assert result.to_record() == {
        "status": "valid",
        "path": str(KEPT_FRAME_SET),
        "contract": _FRAME_SET,
        "version": "1.0.0",
        "urn": _URN,
        "seal_checked": True,
    }


def test_a_generated_case_line_validates(tmp_path: Path) -> None:
    record = _kept()
    parent = record["bundles"][0]
    case = parent | {"stream_id": "shaken", "parent_stream_id": parent["stream_id"]}
    record["bundles"] = [parent, case]

    assert validate_file(_write(tmp_path, _resealed(record))).contract == _FRAME_SET


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
    record = _kept()
    alter(record)

    refusal = _refused(_write(tmp_path, _resealed(record)))

    assert refusal.code is RefusalCode.RECORD_INVALID
    assert refusal.details["urn"] == _URN
    violations = refusal.details["violations"]
    assert isinstance(violations, list)
    assert pointer in [item["pointer"] for item in violations]  # type: ignore[index, call-overload]
    assert refusal.details["limit"] == VIOLATION_LIMIT


def test_a_record_whose_content_moved_is_tampered_though_its_shape_is_fine(tmp_path: Path) -> None:
    record = _kept()
    record["corpus_manifest_sha256"] = _HASH

    refusal = _refused(_write(tmp_path, record))

    assert refusal.code is RefusalCode.RECORD_TAMPERED
    assert refusal.details == {"record": "record.json"}


def test_a_family_with_no_seal_is_not_held_to_one(
    contract_root: Path, register: Register, tmp_path: Path
) -> None:
    register(versioned_schema("declaration", "plain", "1.0.0"))
    path = _write(tmp_path, {"schema_version": 1, "name": "x"})

    result = validate_file(path, contract_name="declaration/plain", root=contract_root)

    assert not result.seal_checked


def test_a_declaration_that_breaks_its_contract_is_manifest_invalid(
    contract_root: Path, register: Register, tmp_path: Path
) -> None:
    register(versioned_schema("declaration", "plain", "1.0.0"))
    path = _write(tmp_path, {"schema_version": 1, "surprise": True})

    refusal = _refused(path, contract_name="declaration/plain", root=contract_root)

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

    refusal = _refused(path)

    assert refusal.code is RefusalCode.RECORD_INVALID
    assert reason in refusal.message


def test_a_file_that_is_not_text_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\xfa")

    assert _refused(path).code is RefusalCode.RECORD_INVALID


@pytest.mark.parametrize("document", [{"name": "x"}, [1, 2], "text", 3, None])
def test_a_file_that_does_not_name_its_format_must_be_given_one(
    tmp_path: Path, document: object
) -> None:
    refusal = _refused(_write(tmp_path, document))

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert "--contract" in refusal.message


def test_a_kind_with_no_contract_is_named(tmp_path: Path) -> None:
    refusal = _refused(_write(tmp_path, {"kind": "ss-track.unknown", "schema_version": 1}))

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert refusal.details == {"kind": "ss-track.unknown"}


def test_an_unknown_contract_lists_the_known_ones() -> None:
    refusal = _refused(KEPT_FRAME_SET, contract_name="record/nothing")

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert _FRAME_SET in refusal.details["contracts"]  # type: ignore[operator]


def test_an_unknown_version_lists_the_frozen_ones() -> None:
    refusal = _refused(KEPT_FRAME_SET, contract_name=_FRAME_SET, version="7.0.0")

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert refusal.details["versions"] == ["1.0.0"]


def test_a_named_version_is_used_exactly() -> None:
    result = validate_file(KEPT_FRAME_SET, contract_name=_FRAME_SET, version="1.0.0")

    assert result.version == "1.0.0"


def test_the_contract_of_another_format_refuses_the_file() -> None:
    other = KEPT_FRAME_SET.with_name("corpus-schema-3-129a350.json")

    assert _refused(other, contract_name=_FRAME_SET).code is RefusalCode.RECORD_INVALID


def test_shared_types_state_no_document_so_they_accept_none() -> None:
    refusal = _refused(KEPT_FRAME_SET, contract_name="shared/types")

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert refusal.details == {"contract": "shared/types"}


def test_a_draft_in_the_set_does_not_stop_a_kind_being_found(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    draft = {
        "family": "record",
        "id": "a-draft",
        "owner": "data-contracts",
        "status": "draft",
        "description": "Not yet stated.",
        "reason": "The dialect cannot state it.",
        "versions": [],
    }
    registry["contracts"].insert(0, draft)
    write_registry(contract_root, registry)

    assert validate_file(KEPT_FRAME_SET, root=contract_root).contract == _FRAME_SET


def test_a_draft_has_nothing_to_validate_against(contract_root: Path, tmp_path: Path) -> None:
    registry = read_registry(contract_root)
    draft = {
        "family": "record",
        "id": "z-draft",
        "owner": "data-contracts",
        "status": "draft",
        "description": "Not yet stated.",
        "reason": "The dialect cannot state it.",
        "versions": [],
    }
    registry["contracts"].insert(1, draft)
    write_registry(contract_root, registry)

    refusal = _refused(
        _write(tmp_path, {"schema_version": 1}), contract_name="record/z-draft", root=contract_root
    )

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert refusal.details["reason"] == "The dialect cannot state it."


def test_the_newest_of_the_stamped_major_is_chosen_numerically(
    contract_root: Path, register: Register, tmp_path: Path
) -> None:
    path = register(versioned_schema("declaration", "versioned", "1.2.0"))
    registry = read_registry(contract_root)
    entry = next(item for item in registry["contracts"] if item["id"] == "versioned")
    (first,) = entry["versions"]
    entries = [first]
    for version in ("1.10.0", "2.0.0"):
        schema = versioned_schema("declaration", "versioned", version)
        later = path.with_name(f"{version}.json")
        later.write_text(json.dumps(schema), encoding="utf-8")
        entries.append(version_entry(later))
    entry["versions"] = entries
    write_registry(contract_root, registry)

    def chosen(record: dict[str, object]) -> str:
        document = _write(tmp_path, record)
        return validate_file(
            document, contract_name="declaration/versioned", root=contract_root
        ).version

    assert chosen({"schema_version": 1}) == "1.10.0"
    assert chosen({"schema_version": 2}) == "2.0.0"
    assert chosen({"name": "no stamp"}) == "2.0.0"


def test_an_installed_frozen_file_that_was_edited_refuses_every_validation(
    contract_root: Path,
) -> None:
    path = frame_set_path(contract_root)
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    refusal = _refused(KEPT_FRAME_SET, root=contract_root)

    assert refusal.code is RefusalCode.CONTRACT_SET_INVALID
    assert _URN in refusal.message


def test_a_frozen_file_that_went_missing_refuses_every_validation(contract_root: Path) -> None:
    frame_set_path(contract_root).unlink()

    assert _refused(KEPT_FRAME_SET, root=contract_root).code is RefusalCode.CONTRACT_SET_INVALID


def test_a_damaged_registry_refuses_the_listing(contract_root: Path) -> None:
    (contract_root / "registry.yaml").write_text("contracts: 3\n", encoding="utf-8")

    with pytest.raises(CorpusRefusal) as caught:
        list_contracts(contract_root)

    assert caught.value.code is RefusalCode.CONTRACT_SET_INVALID


def test_a_listing_states_each_contract_and_its_pins() -> None:
    record = list_contracts().to_record()

    assert record["status"] == "listed"
    contracts = {item["contract"]: item for item in record["contracts"]}  # type: ignore[union-attr, index, call-overload, misc]
    frame_set = contracts[_FRAME_SET]
    assert frame_set["family"] == "record"
    assert frame_set["owner"] == "corpus-provenance"
    assert frame_set["status"] == "active"
    version = frame_set["versions"][0]
    assert version["urn"] == _URN
    assert len(version["structure"]) == len(version["meaning"]) == 64
    assert version["change"]["class"] == "initial"


def test_the_parser_selects_the_contract_commands() -> None:
    parsed = build_parser().parse_args(["contracts", "list"])
    assert (parsed.command, parsed.contracts_command) == ("contracts", "list")
    parsed = build_parser().parse_args(
        ["contracts", "validate", "--file", "a", "--contract", "b", "--version", "1.0.0"]
    )
    assert (parsed.file, parsed.contract, parsed.version) == (Path("a"), "b", "1.0.0")


def _last(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    record: dict[str, object] = json.loads(caplog.records[-1].getMessage())
    return record


def test_the_commands_need_no_data_root(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    monkeypatch.setattr("ss_track.cli.resolve_data_root", _no_data_root)

    assert main(["contracts", "list"]) == EXIT_OK
    assert main(["contracts", "validate", "--file", str(KEPT_FRAME_SET)]) == EXIT_OK
    assert _last(caplog)["urn"] == _URN


def _no_data_root() -> Path:
    raise AssertionError("a contract command reached for the data root")


def test_a_refusal_is_one_json_record_and_exit_one(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    record = _kept()
    record["surprise"] = 1

    status = main(["contracts", "validate", "--file", str(_write(tmp_path, _resealed(record)))])

    assert status == EXIT_REFUSED
    assert _last(caplog)["code"] == "RECORD_INVALID"


def test_a_missing_file_is_a_refusal_and_no_traceback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    assert main(["contracts", "validate", "--file", str(tmp_path / "none.json")]) == EXIT_REFUSED
    assert _last(caplog)["code"] == "STORAGE_FAILED"


def test_a_result_does_not_take_its_version_from_an_embedded_record(
    contract_root: Path, register: Register, tmp_path: Path
) -> None:
    path = register(versioned_schema("result", "embedded", "1.0.0"))
    later = path.with_name("2.0.0.json")
    schema = versioned_schema("result", "embedded", "1.0.0")
    schema["$id"] = "urn:ss-track:contract:result:embedded:2.0.0"
    later.write_text(json.dumps(schema))
    registry = read_registry(contract_root)
    entry = next(item for item in registry["contracts"] if item["id"] == "embedded")
    entry["versions"].append(version_entry(later))
    write_registry(contract_root, registry)
    result = validate_file(
        _write(tmp_path, {"schema_version": 1}),
        contract_name="result/embedded",
        root=contract_root,
    )
    assert result.version == "2.0.0"
