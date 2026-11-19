"""Installed readers must not trust stale development registry pins."""

from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation import enforce
from tests.schema.conftest import read_registry, write_registry


@pytest.mark.parametrize(
    ("family", "name", "pin"),
    [
        ("record", "frame-set", "structure"),
        ("record", "frame-set", "meaning"),
        ("event", "frame", "meaning"),
    ],
)
def test_installed_reader_refuses_a_stale_pin(
    development_root: Path, monkeypatch: pytest.MonkeyPatch, family: str, name: str, pin: str
) -> None:
    registry = read_registry(development_root)
    entry = next(
        item for item in registry["contracts"] if item["id"] == name and item["family"] == family
    )
    entry["versions"][0]["fingerprints"][pin] = "0" * 64
    write_registry(development_root, registry)
    monkeypatch.setattr(enforce, "load_contract_set", lambda: load_contract_set(development_root))
    enforce.installed_contracts.cache_clear()
    try:
        with pytest.raises(CorpusRefusal) as caught:
            enforce.installed_contracts()
        assert caught.value.code == RefusalCode.CONTRACT_SET_INVALID
    finally:
        enforce.installed_contracts.cache_clear()


def test_contract_commands_refuse_stale_pins(development_root: Path) -> None:
    from ss_track.schema.validation.commands import list_contracts, validate_file
    from tests.schema.conftest import KEPT_FRAME_SET

    registry = read_registry(development_root)
    entry = next(
        item
        for item in registry["contracts"]
        if item["family"] == "record" and item["id"] == "frame-set"
    )
    entry["versions"][0]["fingerprints"]["meaning"] = "0" * 64
    write_registry(development_root, registry)
    with pytest.raises(CorpusRefusal, match="meaning fingerprint is stale"):
        list_contracts(development_root)
    with pytest.raises(CorpusRefusal, match="meaning fingerprint is stale"):
        validate_file(KEPT_FRAME_SET, root=development_root)


def test_installed_reader_refuses_a_broken_stage_rule(
    development_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A development install with a retired major could keep an outdated record readable."""
    registry = read_registry(development_root)
    entry = next(item for item in registry["contracts"] if item["id"] == "frame-set")
    entry["retired_majors"] = [
        {"major": 2, "status": "retired", "reason": "Old.", "migration": "Regenerate."}
    ]
    write_registry(development_root, registry)
    monkeypatch.setattr(enforce, "load_contract_set", lambda: load_contract_set(development_root))
    enforce.installed_contracts.cache_clear()
    try:
        with pytest.raises(CorpusRefusal, match="holds no retired major") as caught:
            enforce.installed_contracts()
        assert caught.value.code == RefusalCode.CONTRACT_SET_INVALID
    finally:
        enforce.installed_contracts.cache_clear()
