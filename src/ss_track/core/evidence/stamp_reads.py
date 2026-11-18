"""What a sealed read must still prove about its data root once it has loaded a record (17.7).

A command checks a root when it starts, and the root can change while it runs: its stamp can
disappear, a first write can stamp an unstamped root, and a write by a newer install can add pins
for contracts the stamp lacked. Only that last change can make a record readable that was not: a
stamp's existing pins never change, because every writer verifies them under the lock. So a read
of a contract the stamp pinned when checked needs no recheck, and a read of one it lacked rechecks
the stamp after loading the record.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.evidence.checked_roots import end_reuse, holding, remember
from ss_track.core.evidence.contract_stamp import (
    installed_fingerprints,
    unstamped_evidence,
    verify_stamp,
)
from ss_track.core.evidence.stamp_file import REGENERATE_REMEDY, STAMP_NAME
from ss_track.core.evidence.unstamped import is_record_shaped
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema.validation.enforce import installed_contracts


@dataclass(frozen=True, slots=True)
class ReadGuard:
    """A read whose loaded record must still be proven: its root is unstamped, or `contract` unpinned."""

    root: Path
    contract: str | None  # None: the root has no stamp, so a record-shaped object is refused


def check_before_read(path: Path, kind: str) -> ReadGuard | None:
    """Recheck the root of a read of `kind` at `path`, or return None when it may simply be read.

    A root that was unstamped, or lost its stamp, is rechecked: a stamp written since is verified.
    A stamped root whose stamp pinned this kind's contract when checked needs nothing more.
    """
    checked = holding(path)
    if checked is None:
        return None
    stamp = checked.root / STAMP_NAME
    contract = _contract_of(kind)
    if not checked.unstamped and stamp.is_file():
        return ReadGuard(checked.root, contract) if contract in checked.missing else None
    installed = installed_fingerprints()
    if installed is None:
        return None
    end_reuse(path)
    missing = verify_stamp(stamp, installed)
    if missing is None:
        return ReadGuard(checked.root, None)
    remember(checked.root, False, missing=missing)
    return ReadGuard(checked.root, contract) if contract in missing else None


def require_proven(guard: ReadGuard, path: Path, loaded: Mapping[str, JsonValue]) -> None:
    """Refuse a loaded record its root cannot prove was written under this install's pins.

    In an unstamped root a record-shaped object is unstamped evidence. A record of a contract the
    stamp lacked when checked is served only if the stamp now pins it as this install does: a
    newer install may have added it since, and `verify_stamp` refuses another pin.
    """
    stamp = guard.root / STAMP_NAME
    if guard.contract is None:
        if is_record_shaped(loaded):
            raise unstamped_evidence(path, stamp)
        return
    installed = installed_fingerprints()
    if installed is None:
        return  # a released install reads by major
    missing = verify_stamp(stamp, installed)
    if missing is None:
        raise unstamped_evidence(path, stamp)
    remember(guard.root, False, missing=missing)
    if guard.contract in missing:
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            f"the data root holds a record of {guard.contract}, which its contract stamp does not pin",
            {
                "record": str(path),
                "stamp": str(stamp),
                "contract": guard.contract,
                "remedy": REGENERATE_REMEDY,
            },
        )


def _contract_of(kind: str) -> str | None:
    contract = installed_contracts().records.get(kind)
    return None if contract is None else contract.name
