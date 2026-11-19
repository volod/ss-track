"""Stage and publish a complete development event descriptor set."""

import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ss_track.contract.image import fingerprints
from ss_track.core.canonical import sha256_bytes
from ss_track.schema.compatibility.batch_publish import publish_batch
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.contract import BASELINE_VERSION, DEVELOPMENT
from ss_track.schema.registry.store import REGISTRY_NAME, registry_document


def repin_events(
    root: Path, candidates: dict[str, tuple[bytes, str]], bindings: dict[Path, bytes]
) -> None:
    """Validate all candidate images and pins together, then publish as one batch."""
    original = (root / REGISTRY_NAME).read_bytes()
    registry = registry_document(original)
    if registry.get("stage") != DEVELOPMENT:
        raise ValueError("contract stage changed during generation; retry")
    previous: dict[Path, bytes | None] = {}
    changes: dict[Path, bytes] = {}
    pins_changed = False
    with tempfile.TemporaryDirectory(prefix="ss-track-event-set-") as temporary:
        staged = Path(temporary) / "contracts"
        shutil.copytree(root, staged)
        for package, (payload, urn) in candidates.items():
            relative, changed = _pin_candidate(registry, package, payload, urn)
            pins_changed |= changed
            target = root / relative
            old = target.read_bytes() if target.is_file() else None
            previous[relative] = old
            if old != payload:
                changes[relative] = payload
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        written = (
            yaml.safe_dump(registry, sort_keys=False, allow_unicode=False).encode("ascii")
            if pins_changed
            else original
        )
        (staged / REGISTRY_NAME).write_bytes(written)
        findings = check_contract_set(staged)
        if findings:
            raise ValueError("event generation refused: " + "; ".join(findings))
    for target, payload in bindings.items():
        old = target.read_bytes() if target.is_file() else None
        previous[target] = old
        if old != payload:
            changes[target] = payload
    if changes or pins_changed:
        publish_batch(root, changes, previous, written, original)


def _pin_candidate(
    registry: dict[str, Any], package: str, payload: bytes, urn: str
) -> tuple[Path, bool]:
    version = urn.rsplit(":", 1)[-1]
    if version != BASELINE_VERSION:
        raise ValueError(f"event/{package}: development requires {BASELINE_VERSION}")
    entry = _event_entry(registry, package, version)
    structure, meaning = fingerprints(payload, urn)
    pins = {"structure": structure, "meaning": meaning}
    digest = sha256_bytes(payload)
    changed = entry["file_sha256"] != digest or entry["fingerprints"] != pins
    entry["file_sha256"] = digest
    entry["fingerprints"] = pins
    return Path("event") / package / f"{version}.binpb", changed


def _event_entry(registry: dict[str, Any], package: str, version: str) -> dict[str, Any]:
    entries = [
        item
        for item in registry["contracts"]
        if item["family"] == "event" and item["id"] == package
    ]
    if len(entries) != 1 or len(entries[0]["versions"]) != 1:
        raise ValueError(f"event/{package}: expected one registered development version")
    entry: dict[str, Any] = entries[0]["versions"][0]
    if entry["version"] != version:
        raise ValueError(f"event/{package}: registry version does not match {version}")
    return entry
