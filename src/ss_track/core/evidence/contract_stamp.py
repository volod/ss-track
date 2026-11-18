"""The development contract set a data root's records were written under (spec section 17.7).

In development, a record written before an in-place edit has the same major as a new record.
The stamp pins structure and meaning of record and shared contracts before the first sealed write.
A stale or incomplete stamp refuses reads until the data is regenerated. In the released stage a
record's major identifies its contract, so the stamp is not used.
"""

import fcntl
import os
from collections.abc import Mapping
from pathlib import Path

from ss_track.core.evidence.checked_roots import (
    end_reuse,
    holding,
    remember,
    reusable_walk,
)
from ss_track.core.evidence.stamp_file import (
    REGENERATE_REMEDY,
    STAMP_NAME,
    read_stamp,
    write_stamp,
)
from ss_track.core.evidence.unstamped import first_unstamped_record
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema.registry.contract import DEVELOPMENT, RECORD_FAMILY, SHARED_FAMILY
from ss_track.schema.validation.enforce import installed_contracts


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


def require_current_data_root(data_root: Path) -> None:
    """Refuse a data root stamped under another development contract set.

    A root that passes joins the roots this command's sealed writes stamp, by `stamp_before_write`;
    checking another root keeps it. Without a stamp the root is walked for sealed evidence, unless
    this command walked it clean with no sealed read or write under it since
    (`core.evidence.checked_roots`).
    """
    _require(data_root, reuse=True)


def _require(data_root: Path, *, reuse: bool) -> None:
    resolved = data_root.resolve()
    reusable = reuse and reusable_walk(resolved)
    remember(resolved, None)
    installed = installed_fingerprints()
    if installed is None:
        return
    path = data_root / STAMP_NAME
    if _verify_stamp(path, installed):
        remember(resolved, False)
        return
    if not reusable:
        found = first_unstamped_record(data_root)
        if found is not None:
            raise unstamped_evidence(found, path)
    remember(resolved, True, walked=True)


def unstamped_evidence(record: Path, stamp: Path) -> CorpusRefusal:
    """Refuse a sealed-looking record in a root that has no development contract stamp."""
    return CorpusRefusal(
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
        "the data root contains sealed evidence but has no development contract stamp",
        {"record": str(record), "stamp": str(stamp), "remedy": REGENERATE_REMEDY},
    )


def _verify_stamp(path: Path, installed: Mapping[str, str]) -> bool:
    """Refuse a stamp that differs from the installed set; return False when there is none."""
    stamped = read_stamp(path)
    if stamped is None:
        return False
    stamped_structure, stamped_meaning = stamped
    meanings = installed_meanings()
    assert meanings is not None
    changed = _changed(stamped_structure, stamped_meaning, installed, meanings)
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
    return True


def changed_contracts(
    structures: Mapping[str, str], meanings: Mapping[str, str]
) -> list[str] | None:
    """Name the record and shared contracts whose pins differ from the installed set.

    This is the stamp's comparison, for pins that travel with evidence, such as a development
    handoff. A contract named on only one side differs. Returns None in the released stage.
    """
    installed = installed_fingerprints()
    if installed is None:
        return None
    installed_meaning = installed_meanings()
    assert installed_meaning is not None
    return _changed(structures, meanings, installed, installed_meaning)


def _changed(
    structures: Mapping[str, str],
    meanings: Mapping[str, str] | None,
    installed: Mapping[str, str],
    installed_meaning: Mapping[str, str],
) -> list[str]:
    """Compare pins with the installed set; structure-only pins compare record structure alone."""
    names = structures.keys() | installed.keys() | installed_meaning.keys()
    if meanings is not None:
        names |= meanings.keys()
    return sorted(
        name
        for name in names
        if (
            (meanings is not None or name.startswith("record/"))
            and structures.get(name) != installed.get(name)
        )
        or (meanings is not None and meanings.get(name) != installed_meaning.get(name))
    )


def stamp_before_write(path: Path) -> None:
    """Check and stamp the root under a lock before publishing a sealed record.

    The locked check always walks an unstamped root, and the write ends walk reuse for every
    checked root holding `path`, since an enclosing root then holds the new record.
    """
    checked = holding(path)
    installed = installed_fingerprints()
    if checked is None or installed is None:
        return
    root = checked.root
    end_reuse(path)
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _require(root, reuse=False)
        stamp = root / STAMP_NAME
        if not stamp.exists():
            meanings = installed_meanings()
            assert meanings is not None
            write_stamp(stamp, installed, meanings)
            remember(root, False)
    finally:
        os.close(descriptor)


def check_before_read(path: Path) -> Path | None:
    """Return the stamp the root of a record read at `path` lacks, or None when it may be read.

    A root that was unstamped, or lost its stamp, is rechecked: a stamp written since is verified.
    Without one, `core.evidence.sealed` refuses the record it loads when it holds both record keys.
    No walk is needed, because only such a file can pass a sealed read, and in an unstamped root it
    is unstamped evidence whatever else the root holds.
    """
    checked = holding(path)
    if checked is None:
        return None
    stamp = checked.root / STAMP_NAME
    if not checked.unstamped and stamp.is_file():
        return None
    installed = installed_fingerprints()
    if installed is None:
        return None
    end_reuse(path)
    if _verify_stamp(stamp, installed):
        remember(checked.root, False)
        return None
    return stamp
