"""What a sealed read must still prove about its data root once it has loaded a record (17.7).

A command checks a root when it starts, and the root can change while it runs: its stamp can
disappear, a first write can stamp an unstamped root, and a write by a newer install can add pins
for contracts the stamp lacked. A stamp's existing pins never change, because every writer verifies
them under the lock. So a read of a contract the stamp pinned when checked needs no recheck. A read
in a root that had no stamp, or of a contract the stamp lacked, judges the loaded record by the
stamp the root holds after loading it, which also covers a stamp and record written in between.
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
    """A read whose loaded record must still be proven against the root's stamp.

    `unstamped` says the root had no stamp when checked, so a loaded object that is not
    record-shaped needs nothing more. `contract` is the record contract of the kind read, which the
    stamp must pin as this install does; None for a kind the stamp does not cover.
    """

    root: Path
    contract: str | None
    unstamped: bool


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
        return _guard(checked.root, contract, checked.missing)
    installed = installed_fingerprints()
    if installed is None:
        return None
    end_reuse(path)
    missing = verify_stamp(stamp, installed)
    if missing is None:
        return ReadGuard(checked.root, contract, unstamped=True)
    remember(checked.root, False, missing=missing)
    return _guard(checked.root, contract, missing)


def require_proven(guard: ReadGuard, path: Path, loaded: Mapping[str, JsonValue]) -> None:
    """Refuse a loaded record its root cannot prove was written under this install's pins.

    The stamp is read again after loading, because another command may have stamped the root, or
    added this contract's pins, since the check. A record-shaped object in a root that still has no
    stamp is unstamped evidence. Otherwise the record is served only if the stamp now pins its
    contract as this install does: `verify_stamp` refuses another pin, and one still unpinned
    refuses here, which catches a record copied in by hand.
    """
    if guard.unstamped and not is_record_shaped(loaded):
        return
    installed = installed_fingerprints()
    if installed is None:
        return  # a released install reads by major
    stamp = guard.root / STAMP_NAME
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


def _guard(root: Path, contract: str | None, missing: frozenset[str]) -> ReadGuard | None:
    return ReadGuard(root, contract, unstamped=False) if contract in missing else None


def _contract_of(kind: str) -> str | None:
    contract = installed_contracts().records.get(kind)
    return None if contract is None else contract.name
