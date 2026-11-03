"""Check production writer outputs throughout the suite, before tests corrupt fixtures."""

import json
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from ss_track import cli
from ss_track.canonical import SEAL_FIELD, seal_of
from ss_track.corpus import sealed
from ss_track.schema.store import Contract, load_contract_set
from ss_track.schema.strict import violations


def _require_retired_archive(path: Path, record: Mapping[str, Any], contract: Contract) -> None:
    """An amendment copies historic evidence; it does not emit it as a current record."""
    assert contract.name == "record/source-manifest"
    assert record["schema_version"] in [entry["major"] for entry in contract.retired_majors]
    assert path.parent.name == "replaced" and path.stem == record[SEAL_FIELD]
    original = json.loads((path.parent.parent / "manifest.json").read_bytes())
    assert record == original
    assert record[SEAL_FIELD] == seal_of(record)


@pytest.fixture(scope="session", autouse=True)
def validate_written_contracts() -> Iterator[Counter[str]]:
    """Intercept production writes, including imported aliases, without changing runtime readers."""
    contracts = load_contract_set()
    registry = contracts.schema_registry()
    schemas = {
        contract.name: contracts.frozen_schema(contract, contract.versions[-1])
        for contract in contracts.contracts
        if contract.versions and contract.family != "shared"
    }
    kinds = {
        schema["properties"]["kind"]["const"]: name
        for name, schema in schemas.items()
        if name.startswith("record/")
    }
    seen: Counter[str] = Counter()
    write = sealed.write_sealed
    log = cli._log_json

    def check(name: str, record: Mapping[str, Any]) -> None:
        # Serialization makes Python tuples and StrEnums agree with the written JSON.
        document = json.loads(json.dumps(record, allow_nan=False))
        found = violations(document, schemas[name], registry)
        assert not found, f"{name}: {found}"
        seen[name] += 1

    def checked_write(path: Path, record: Mapping[str, Any]) -> None:
        kind = record.get("kind")
        assert kind in kinds, f"unregistered production record: {kind}"
        name = kinds[kind]
        if record.get("schema_version") != schemas[name]["properties"]["schema_version"]["const"]:
            _require_retired_archive(path, record, contracts.named(name))
        else:
            check(name, record)
        write(path, record)

    def checked_log(level: int, record: dict[str, object]) -> None:
        check("result/command", record)
        log(level, record)

    with pytest.MonkeyPatch.context() as patch:
        for name, module in tuple(sys.modules.items()):
            if (
                name.startswith("ss_track.corpus.")
                and getattr(module, "write_sealed", None) is write
            ):
                patch.setattr(module, "write_sealed", checked_write)
        patch.setattr(cli, "_log_json", checked_log)
        yield seen
