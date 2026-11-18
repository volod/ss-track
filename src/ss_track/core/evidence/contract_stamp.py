"""The development contract set a data root's records were written under (spec section 17.7).

In development, a record written before an in-place edit has the same major as a new record.
The stamp pins structure and meaning of record and shared contracts before the first sealed write.
A stamp with another pin, a contract the install lacks, or no meaning fingerprints refuses reads
until the data is regenerated. A contract added since the stamp was written cannot have records in
the root yet, so it does not refuse: the root's next sealed write adds its pins, and
`core.evidence.stamp_reads` keeps a read of it from serving a record pinned otherwise. In the
released stage a record's major identifies its contract, so the stamp is not used.
"""

from collections.abc import Callable, Mapping
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
from ss_track.core.scratch import directory_lock
from ss_track.schema.registry.contract import DEVELOPMENT, STAMPED_FAMILIES, FrozenVersion
from ss_track.schema.validation.enforce import installed_contracts


def installed_fingerprints() -> dict[str, str] | None:
    """Return record and shared structure fingerprints, or None after release."""
    return _installed_pins(lambda frozen: frozen.structure)


def installed_meanings() -> dict[str, str] | None:
    """Return record and shared meaning fingerprints, or None after release."""
    return _installed_pins(lambda frozen: frozen.meaning)


def _installed_pins(pin: Callable[[FrozenVersion], str]) -> dict[str, str] | None:
    """Return one pin of each contract the stamp covers (`STAMPED_FAMILIES`), in development."""
    contracts = installed_contracts().contracts
    if contracts.stage != DEVELOPMENT:
        return None
    return {
        contract.name: pin(contract.versions[-1])
        for contract in contracts.contracts
        if contract.family in STAMPED_FAMILIES and contract.versions
    }


def require_current_data_root(data_root: Path) -> None:
    """Refuse a data root stamped under another development contract set.

    A root that passes joins the roots this command's sealed writes stamp, by `stamp_before_write`;
    checking another root keeps it. Without a stamp the root is walked for sealed evidence, unless
    this command walked it clean with no sealed read or write under it since
    (`core.evidence.checked_roots`). A stamp that lacks only contracts added since it was written
    passes, and the root's next sealed write adds them.
    """
    _require(data_root, reuse=True)


def _require(data_root: Path, *, reuse: bool) -> frozenset[str]:
    """Check a root and return the installed contracts its stamp lacks; none when it has no stamp."""
    resolved = data_root.resolve()
    reusable = reuse and reusable_walk(resolved)
    remember(resolved, None)
    installed = installed_fingerprints()
    if installed is None:
        return frozenset()
    path = data_root / STAMP_NAME
    missing = verify_stamp(path, installed)
    if missing is not None:
        remember(resolved, False, missing=missing)
        return missing
    if not reusable:
        found = first_unstamped_record(data_root)
        if found is not None:
            raise unstamped_evidence(found, path)
    remember(resolved, True, walked=True)
    return frozenset()


def unstamped_evidence(record: Path, stamp: Path) -> CorpusRefusal:
    """Refuse a sealed-looking record in a root that has no development contract stamp."""
    return CorpusRefusal(
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
        "the data root contains sealed evidence but has no development contract stamp",
        {"record": str(record), "stamp": str(stamp), "remedy": REGENERATE_REMEDY},
    )


def verify_stamp(path: Path, installed: Mapping[str, str]) -> frozenset[str] | None:
    """Refuse a stamp that differs from the installed set, or return the contracts it lacks.

    None means there is no stamp. A contract only the install pins was added after the stamp was
    written, and no record of it can be in the root yet, so it is returned rather than refused. A
    contract whose pins differ, or that only the stamp names, refuses.
    """
    stamped = read_stamp(path)
    if stamped is None:
        return None
    stamped_structure, stamped_meaning = stamped
    meanings = installed_meanings()
    assert meanings is not None
    if stamped_meaning is None:
        changed = _changed(stamped_structure, None, installed, meanings)
    else:
        changed = _conflicts(stamped_structure, stamped_meaning, installed, meanings)
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
    return frozenset(installed.keys() - stamped_structure.keys())


def _conflicts(
    structures: Mapping[str, str],
    meanings: Mapping[str, str],
    installed: Mapping[str, str],
    installed_meaning: Mapping[str, str],
) -> list[str]:
    """Name each contract the stamp pins otherwise than the install does, or the install lacks."""
    return sorted(
        name
        for name in structures.keys() | meanings.keys()
        if structures.get(name) != installed.get(name)
        or meanings.get(name) != installed_meaning.get(name)
    )


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
    checked root holding `path`, since an enclosing root then holds the new record. A stamp that
    lacks contracts added since it was written is replaced by the installed set, which then holds
    every contract this command can write.
    """
    checked = holding(path)
    installed = installed_fingerprints()
    if checked is None or installed is None:
        return
    root = checked.root
    end_reuse(path)
    root.mkdir(parents=True, exist_ok=True)
    with directory_lock(root):
        missing = _require(root, reuse=False)
        stamp = root / STAMP_NAME
        if missing or not stamp.exists():
            meanings = installed_meanings()
            assert meanings is not None
            write_stamp(stamp, installed, meanings)
            remember(root, False)
