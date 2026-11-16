"""The development contract set a data root's records were written under (spec section 17.7).

In the development stage a contract is edited in place, so a record written before the edit still
stamps `schema_version: 1` and its major cannot tell it apart. The data root therefore keeps the
structure fingerprint of every record contract its records were written under, in one stamp file
beside them. A command on a root stamped under another set is refused with the remedy to
regenerate the root. A command on a root with no stamp stamps it with the installed set when it
first writes a sealed record there, so a read-only command writes nothing. A description-only
edit moves no structure fingerprint, so it never asks for regeneration. In the released stage a
record's major says what it is, so no stamp is written or read.
"""

import json
from collections.abc import Mapping
from contextvars import ContextVar
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.schema.registry.contract import DEVELOPMENT, RECORD_FAMILY
from ss_track.schema.validation.enforce import installed_contracts

STAMP_NAME = "contract-set.json"
STAMP_KIND = "ss-track.development-contract-set"
REGENERATE_REMEDY = (
    "this data root was written under an earlier development contract set: delete its sealed "
    "datasets and the stamp, keep operator-written declarations, labels and review decisions, and "
    "regenerate the datasets from them with this ss-track (spec section 17.7)"
)


def installed_fingerprints() -> dict[str, str] | None:
    """Return each record contract's structure fingerprint, or None once the set is released."""
    contracts = installed_contracts().contracts
    if contracts.stage != DEVELOPMENT:
        return None
    return {
        contract.name: contract.versions[-1].structure
        for contract in contracts.contracts
        if contract.family == RECORD_FAMILY and contract.versions
    }


_CHECKED_ROOT: ContextVar[Path | None] = ContextVar("checked_data_root", default=None)


def require_current_data_root(data_root: Path) -> None:
    """Refuse a data root stamped under another development contract set.

    A root that passes becomes the one this command's sealed writes stamp, by `record_written`.
    """
    installed = installed_fingerprints()
    if installed is None:
        return
    path = data_root / STAMP_NAME
    stamped = _read_stamp(path)
    _CHECKED_ROOT.set(data_root.resolve())
    if stamped is None:
        return
    changed = sorted(
        name
        for name in stamped.keys() | installed.keys()
        if stamped.get(name) != installed.get(name)
    )
    if changed:
        listed: list[JsonValue] = list(changed)
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            "the data root was written under another development contract set",
            {"stamp": str(path), "changed_contracts": listed, "remedy": REGENERATE_REMEDY},
        )


def record_written(path: Path) -> None:
    """Stamp the checked data root when a sealed record is first written below it."""
    root = _CHECKED_ROOT.get()
    installed = installed_fingerprints()
    if root is None or installed is None or not path.resolve().is_relative_to(root):
        return
    stamp = root / STAMP_NAME
    if not stamp.exists():
        _write_stamp(stamp, installed)


def _read_stamp(path: Path) -> Mapping[str, object] | None:
    """Parse the stamp, the one file of a data root that is not a sealed record."""
    try:
        text = path.read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    try:
        document = json.loads(text)
    except ValueError as error:
        raise _damaged(path, f"not JSON: {error}") from error
    if not isinstance(document, dict) or document.get("kind") != STAMP_KIND:
        raise _damaged(path, "not a development contract-set stamp")
    contracts = document.get("contracts")
    if not isinstance(contracts, dict):
        raise _damaged(path, "not a development contract-set stamp")
    return contracts


def _write_stamp(path: Path, installed: Mapping[str, str]) -> None:
    document = {"kind": STAMP_KIND, "contracts": dict(sorted(installed.items()))}
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, (json.dumps(document, indent=2) + "\n").encode("ascii"))


def _damaged(path: Path, reason: str) -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.RECORD_TAMPERED,
        f"{path.name} is damaged: {reason}",
        {"stamp": str(path), "remedy": REGENERATE_REMEDY},
    )
