"""`ss-track contracts`: version choice, a damaged installed set, the listing and the CLI record."""

import json
import logging
from pathlib import Path

import pytest

from ss_track.cli import build_parser, main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.schema import list_contracts, validate_file
from tests.schema.conftest import (
    KEPT_FRAME_SET,
    Register,
    frame_set_path,
    read_registry,
    version_entry,
    versioned_schema,
    write_registry,
)
from tests.schema.validation._command_files import (
    FRAME_SET_CONTRACT,
    FRAME_SET_URN,
    kept_record,
    refused_validation,
    resealed,
    write_json,
)


def test_an_unknown_contract_lists_the_known_ones() -> None:
    refusal = refused_validation(KEPT_FRAME_SET, contract_name="record/nothing")

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert FRAME_SET_CONTRACT in refusal.details["contracts"]  # type: ignore[operator]


def test_an_unknown_version_lists_the_frozen_ones() -> None:
    refusal = refused_validation(KEPT_FRAME_SET, contract_name=FRAME_SET_CONTRACT, version="7.0.0")

    assert refusal.code is RefusalCode.CONTRACT_UNKNOWN
    assert refusal.details["versions"] == ["1.0.0"]


def test_a_named_version_is_used_exactly() -> None:
    result = validate_file(KEPT_FRAME_SET, contract_name=FRAME_SET_CONTRACT, version="1.0.0")

    assert result.version == "1.0.0"


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

    assert validate_file(KEPT_FRAME_SET, root=contract_root).contract == FRAME_SET_CONTRACT


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

    refusal = refused_validation(
        write_json(tmp_path, {"schema_version": 1}),
        contract_name="record/z-draft",
        root=contract_root,
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
        document = write_json(tmp_path, record)
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

    refusal = refused_validation(KEPT_FRAME_SET, root=contract_root)

    assert refusal.code is RefusalCode.CONTRACT_SET_INVALID
    assert FRAME_SET_URN in refusal.message


def test_a_frozen_file_that_went_missing_refuses_every_validation(contract_root: Path) -> None:
    frame_set_path(contract_root).unlink()

    assert (
        refused_validation(KEPT_FRAME_SET, root=contract_root).code
        is RefusalCode.CONTRACT_SET_INVALID
    )


def test_a_damaged_registry_refuses_the_listing(contract_root: Path) -> None:
    (contract_root / "registry.yaml").write_text("contracts: 3\n", encoding="utf-8")

    with pytest.raises(CorpusRefusal) as caught:
        list_contracts(contract_root)

    assert caught.value.code is RefusalCode.CONTRACT_SET_INVALID


def test_a_listing_states_each_contract_and_its_pins() -> None:
    record = list_contracts().to_record()

    assert record["status"] == "listed"
    contracts = {item["contract"]: item for item in record["contracts"]}  # type: ignore[union-attr, index, call-overload, misc]
    frame_set = contracts[FRAME_SET_CONTRACT]
    assert frame_set["family"] == "record"
    assert frame_set["owner"] == "corpus-provenance"
    assert frame_set["status"] == "active"
    version = frame_set["versions"][0]
    assert version["urn"] == FRAME_SET_URN
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
    monkeypatch.setattr("ss_track.commands.report.resolve_data_root", _no_data_root)

    assert main(["contracts", "list"]) == EXIT_OK
    assert main(["contracts", "validate", "--file", str(KEPT_FRAME_SET)]) == EXIT_OK
    assert _last(caplog)["urn"] == FRAME_SET_URN


def _no_data_root() -> Path:
    raise AssertionError("a contract command reached for the data root")


def test_a_refusal_is_one_json_record_and_exit_one(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    record = kept_record()
    record["surprise"] = 1

    status = main(["contracts", "validate", "--file", str(write_json(tmp_path, resealed(record)))])

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
        write_json(tmp_path, {"schema_version": 1}),
        contract_name="result/embedded",
        root=contract_root,
    )
    assert result.version == "2.0.0"
