"""Event packages are frozen descriptors. Freeze and document validation do not parse them."""

from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.schema.compatibility.freeze import freeze_contract
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.validation.commands import list_contracts, validate_file
from tests.schema.conftest import read_registry, write_registry

_FRAME = "event/frame 1.0.0"


def test_an_edited_descriptor_fails(contract_root: Path) -> None:
    path = contract_root / "event" / "frame" / "1.0.0.binpb"
    path.write_bytes(path.read_bytes() + b"\x00")

    findings = check_contract_set(contract_root)

    assert any(item.startswith(f"{_FRAME}: frozen file was edited") for item in findings)


def test_a_stale_event_fingerprint_fails(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    entry = next(
        item
        for item in registry["contracts"]
        if item["family"] == "event" and item["id"] == "frame"
    )
    entry["versions"][0]["fingerprints"]["meaning"] = "0" * 64
    write_registry(contract_root, registry)

    findings = check_contract_set(contract_root)

    assert any(f"{_FRAME}: meaning fingerprint is stale" in item for item in findings)


def test_freeze_refuses_an_event_package(tmp_path: Path) -> None:
    with pytest.raises(CorpusRefusal, match="proto build") as caught:
        freeze_contract("event/frame", tmp_path / "frame.binpb", summary="No.")

    assert caught.value.code == RefusalCode.CONTRACT_SET_INVALID


def test_validate_refuses_protobuf_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "frame.json"
    path.write_text("{}\n", encoding="ascii")

    with pytest.raises(CorpusRefusal, match="protobuf-JSON") as caught:
        validate_file(path, contract_name="event/frame")

    assert caught.value.code == RefusalCode.CONTRACT_UNKNOWN


def test_the_registry_lists_event_contracts() -> None:
    names = {contract.name for contract in list_contracts().contracts}

    assert {"event/analytics", "event/clock", "event/frame", "event/trial", "event/wire"} <= names
