"""Check production writer outputs throughout the suite, before tests corrupt fixtures.

Production `seal` already validates each record. This hook is the independent second statement: it
reads the contracts its own way, and it also covers command results.
"""

import json
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from ss_track.commands import report
from ss_track.core.evidence import sealing
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations

pytest_plugins = ["tests.grouping"]


@pytest.fixture(scope="session", autouse=True)
def validate_written_contracts() -> Iterator[Counter[str]]:
    """Intercept production writes, including imported aliases, without changing runtime code."""
    contracts = load_contract_set()
    registry = contracts.schema_registry()
    schemas = {
        contract.name: contracts.frozen_schema(contract, contract.versions[-1])
        for contract in contracts.contracts
        if contract.versions and contract.family not in {"shared", "event"}
    }
    kinds = {
        schema["properties"]["kind"]["const"]: name
        for name, schema in schemas.items()
        if name.startswith("record/")
    }
    seen: Counter[str] = Counter()
    write = sealing.write_sealed
    log = report.log_json

    def check(name: str, record: Mapping[str, Any]) -> None:
        # Serialization makes Python tuples and StrEnums agree with the written JSON.
        document = json.loads(json.dumps(record, allow_nan=False))
        found = violations(document, schemas[name], registry)
        assert not found, f"{name}: {found}"
        seen[name] += 1

    def checked_write(path: Path, record: Mapping[str, Any]) -> None:
        kind = record.get("kind")
        assert kind in kinds, f"unregistered production record: {kind}"
        check(kinds[kind], record)
        write(path, record)

    def checked_log(level: int, record: dict[str, object]) -> None:
        check("result/command", record)
        log(level, record)

    with pytest.MonkeyPatch.context() as patch:
        for name, module in tuple(sys.modules.items()):
            if name.startswith("ss_track.") and getattr(module, "write_sealed", None) is write:
                patch.setattr(module, "write_sealed", checked_write)
        patch.setattr(report, "log_json", checked_log)
        yield seen
