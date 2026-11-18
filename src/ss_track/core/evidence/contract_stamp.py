"""The development contract set a data root's records were written under (spec section 17.7).

In development, a record written before an in-place edit has the same major as a new record.
The stamp pins structure and meaning of record and shared contracts before the first sealed write.
A stale or incomplete stamp refuses reads until the data is regenerated. In the released stage a
record's major identifies its contract, so the stamp is not used.
"""

import fcntl
import json
import os
import re
from collections.abc import Mapping
from contextvars import ContextVar
from pathlib import Path

from ss_track.core.evidence.unstamped import first_unstamped_record
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.core.strict_json import reject_constant, unique_object
from ss_track.schema.registry.contract import DEVELOPMENT, RECORD_FAMILY, SHARED_FAMILY
from ss_track.schema.validation.enforce import installed_contracts

STAMP_NAME = "contract-set.json"
STAMP_KIND = "ss-track.development-contract-set"
REGENERATE_REMEDY = (
    "this data root may have been written under an earlier development contract set: delete its sealed "
    "datasets and the stamp, keep operator-written declarations, labels and review decisions, and "
    "regenerate the datasets from them with this ss-track (spec section 17.7)"
)


def installed_fingerprints() -> dict[str, str] | None:
    """Return record and shared structure fingerprints, or None after release."""
    contracts = installed_contracts().contracts
    if contracts.stage != DEVELOPMENT:
        return None
    return {
        contract.name: contract.versions[-1].structure
        for contract in contracts.contracts
        if contract.family in (RECORD_FAMILY, SHARED_FAMILY) and contract.versions
    }


def installed_meanings() -> dict[str, str] | None:
    """Return record and shared meaning fingerprints, or None after release."""
    contracts = installed_contracts().contracts
    if contracts.stage != DEVELOPMENT:
        return None
    return {
        contract.name: contract.versions[-1].meaning
        for contract in contracts.contracts
        if contract.family in (RECORD_FAMILY, SHARED_FAMILY) and contract.versions
    }


# Every root this command has checked, each with whether it had no stamp when checked. A check of
# one root never drops another, so a nested check cannot stop the outer root's stamping.
_CHECKED_ROOTS: ContextVar[tuple[tuple[Path, bool], ...]] = ContextVar(
    "checked_data_roots", default=()
)


def _set_checked(root: Path, unstamped: bool | None) -> None:
    """Record `root` as checked, or forget it when `unstamped` is None."""
    kept = tuple(item for item in _CHECKED_ROOTS.get() if item[0] != root)
    _CHECKED_ROOTS.set(kept if unstamped is None else (*kept, (root, unstamped)))


def _checked_root(path: Path) -> tuple[Path, bool] | None:
    """Return the most specific checked root that holds `path`, directly or through a link."""
    spellings = (path.absolute(), path.resolve())
    holding = [
        item
        for item in _CHECKED_ROOTS.get()
        if any(spelling.is_relative_to(item[0]) for spelling in spellings)
    ]
    return max(holding, key=lambda item: len(item[0].parts), default=None)


def require_current_data_root(data_root: Path) -> None:
    """Refuse a data root stamped under another development contract set.

    A root that passes joins the roots this command's sealed writes stamp, by `stamp_before_write`;
    checking another root keeps it.
    """
    resolved = data_root.resolve()
    _set_checked(resolved, None)
    installed = installed_fingerprints()
    if installed is None:
        return
    path = data_root / STAMP_NAME
    stamped = _read_stamp(path)
    if stamped is None:
        found = first_unstamped_record(data_root)
        if found is not None:
            raise CorpusRefusal(
                RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
                "the data root contains sealed evidence but has no development contract stamp",
                {"record": str(found), "stamp": str(path), "remedy": REGENERATE_REMEDY},
            )
        _set_checked(resolved, True)
        return
    stamped_structure, stamped_meaning = stamped
    meanings = installed_meanings()
    assert meanings is not None
    changed = sorted(
        name
        for name in stamped_structure.keys()
        | installed.keys()
        | meanings.keys()
        | (stamped_meaning.keys() if stamped_meaning is not None else set())
        if (
            (stamped_meaning is not None or name.startswith("record/"))
            and stamped_structure.get(name) != installed.get(name)
        )
        or (stamped_meaning is not None and stamped_meaning.get(name) != meanings.get(name))
    )
    if changed or stamped_meaning is None:
        listed: list[JsonValue] = list(changed)
        details: dict[str, JsonValue] = {
            "stamp": str(path),
            "changed_contracts": listed,
            "remedy": REGENERATE_REMEDY,
        }
        if stamped_meaning is None:
            details["unverified_contracts"] = list(sorted(meanings))
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            "the data root cannot be verified against the development contract set",
            details,
        )
    _set_checked(resolved, False)


def stamp_before_write(path: Path) -> None:
    """Check and stamp the root under a lock before publishing a sealed record."""
    checked = _checked_root(path)
    installed = installed_fingerprints()
    if checked is None or installed is None:
        return
    root = checked[0]
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        require_current_data_root(root)
        stamp = root / STAMP_NAME
        if not stamp.exists():
            meanings = installed_meanings()
            assert meanings is not None
            _write_stamp(stamp, installed, meanings)
    finally:
        os.close(descriptor)


def check_before_read(path: Path) -> None:
    """Recheck a root that was unstamped, or lost its stamp, before reading its record."""
    checked = _checked_root(path)
    if checked is None:
        return
    root, unstamped = checked
    if unstamped or not (root / STAMP_NAME).is_file():
        require_current_data_root(root)


def _read_stamp(
    path: Path,
) -> tuple[Mapping[str, str], Mapping[str, str] | None] | None:
    """Parse the stamp, the one file of a data root that is not a sealed record."""
    try:
        text = path.read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    except UnicodeError as error:
        raise _damaged(path, f"not ASCII: {error}") from error
    try:
        document = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, RecursionError) as error:
        raise _damaged(path, f"not JSON: {error}") from error
    if not isinstance(document, dict) or document.get("kind") != STAMP_KIND:
        raise _damaged(path, "not a development contract-set stamp")
    contracts = _fingerprint_map(path, document.get("contracts"))
    raw_meanings = document.get("meanings")
    meanings = (
        None
        if raw_meanings is None and "meanings" not in document
        else _fingerprint_map(path, raw_meanings)
    )
    return contracts, meanings


def _fingerprint_map(path: Path, value: object) -> dict[str, str]:
    if not isinstance(value, dict) or any(
        not isinstance(name, str)
        or not name.startswith(("record/", "shared/"))
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        for name, digest in value.items()
    ):
        raise _damaged(path, "invalid contract fingerprints")
    return value


def _write_stamp(path: Path, installed: Mapping[str, str], meanings: Mapping[str, str]) -> None:
    document = {
        "kind": STAMP_KIND,
        "contracts": dict(sorted(installed.items())),
        "meanings": dict(sorted(meanings.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, (json.dumps(document, indent=2) + "\n").encode("ascii"))


def _damaged(path: Path, reason: str) -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.RECORD_TAMPERED,
        f"{path.name} is damaged: {reason}",
        {"stamp": str(path), "remedy": REGENERATE_REMEDY},
    )
