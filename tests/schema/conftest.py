"""A private copy of the contract set that a test may damage, and helpers to keep it consistent."""

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.canonical import sha256_bytes
from ss_track.schema.fingerprints import meaning_fingerprint, structure_fingerprint
from ss_track.schema.store import contract_urn

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = PROJECT_ROOT / "contracts"
KEPT_FRAME_SET = PROJECT_ROOT / "tests" / "corpus" / "records" / "frame-set-schema-1-fd982a1.json"
STANDARD = "https://json-schema.org/draft/2020-12/schema"
SHA256_REF = "urn:ss-track:contract:shared:types:1.0.0#/$defs/sha256"

type Register = Callable[..., Path]


def read_registry(root: Path) -> dict[str, Any]:
    registry: dict[str, Any] = yaml.safe_load((root / "registry.yaml").read_text(encoding="utf-8"))
    return registry


def write_registry(root: Path, registry: dict[str, Any]) -> None:
    (root / "registry.yaml").write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")


def version_entry(path: Path, **overrides: object) -> dict[str, object]:
    """Pin one file exactly as a freeze would, for a test that then breaks one part."""
    payload = path.read_bytes()
    schema = json.loads(payload)
    entry = {
        "version": path.stem,
        "file_sha256": sha256_bytes(payload),
        "fingerprints": {
            "structure": structure_fingerprint(schema),
            "meaning": meaning_fingerprint(schema),
        },
        "change": {"class": "initial", "summary": "A test contract."},
    }
    return entry | overrides


def contract_schema(
    family: str, contract_id: str, version: str, **fields: object
) -> dict[str, Any]:
    """Return a smallest contract in the dialect that a test may extend."""
    base = {
        "$schema": STANDARD,
        "$id": contract_urn(family, contract_id, version),
        "title": "Test",
        "description": "A test contract.",
        "type": "object",
        "additionalProperties": False,
        "properties": {"name": {"type": "string", "description": "A name."}},
    }
    return base | fields


def versioned_schema(
    family: str, contract_id: str, version: str, **fields: object
) -> dict[str, Any]:
    """Return a smallest declaration or record, stamped with its major."""
    major = int(version.split(".")[0])
    stamp = {"type": "integer", "const": major, "description": "The contract's major."}
    properties = {"schema_version": stamp, "name": {"type": "string", "description": "A name."}}
    return contract_schema(family, contract_id, version, properties=properties) | fields


@pytest.fixture
def contract_root(tmp_path: Path) -> Path:
    root = tmp_path / "contracts"
    shutil.copytree(CONTRACTS, root, ignore=shutil.ignore_patterns("__pycache__"))
    root.joinpath("__init__.py").unlink()
    return root


@pytest.fixture
def register(contract_root: Path) -> Register:
    def add(schema: dict[str, Any], status: str = "active") -> Path:
        """Freeze a contract into the private set, in registry order."""
        _, family, contract_id, version = schema["$id"].rsplit(":", 3)
        path = contract_root / family / contract_id / f"{version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(schema), encoding="utf-8")
        registry = read_registry(contract_root)
        entry = {
            "family": family,
            "id": contract_id,
            "owner": "data-contracts",
            "status": status,
            "description": "A test contract.",
            "versions": [version_entry(path)],
        }
        registry["contracts"].append(entry)
        registry["contracts"].sort(key=lambda item: (item["family"], item["id"]))
        write_registry(contract_root, registry)
        return path

    return add


def frame_set_path(root: Path) -> Path:
    return root / "record" / "frame-set" / "1.0.0.json"
