"""The contract pins a sealed record carries from one development data root to another.

A development record of an edited contract keeps `schema_version: 1`, so matching data hashes do not
prove that two roots read a carried record the same way (spec section 17.7). A record that leaves its
root, such as a review handoff or a host's staged hashes, carries the structure and meaning of every
contract the data-root stamp pins, one row per contract in contract order. Its reader refuses an
absent or differing set before it writes anything. In the released stage the rows are null and a
record's major identifies its contract instead.
"""

from collections.abc import Mapping

from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.read_refusals import incomplete_record
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

CONTRACT_SET_FIELD = "contract_set"


def carried_contract_set() -> list[JsonValue] | None:
    """Return the installed pins as rows in contract order, or None after release."""
    structures = contract_stamp.installed_fingerprints()
    meanings = contract_stamp.installed_meanings()
    if structures is None or meanings is None:
        return None
    return [
        {"contract": name, "structure": structures[name], "meaning": meanings[name]}
        for name in sorted(structures)
    ]


def require_carried_contract_set(
    record: Mapping[str, JsonValue], *, carrier: str, name: str, remedy: str
) -> None:
    """Refuse a carried record whose development pins are absent or differ from this install.

    `carrier` names the record in a message, `name` in the details, and `remedy` says how to get a
    pair written under one contract set. A seal proves only that a record matches itself, so the
    rows are parsed defensively: unsorted, repeated or incomplete rows are tampered.
    """
    if contract_stamp.installed_fingerprints() is None:
        return
    rows = record.get(CONTRACT_SET_FIELD)
    if rows is None:
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            f"{carrier} does not state the development contract set it was written under",
            {"record": name, "field": CONTRACT_SET_FIELD, "remedy": remedy},
        )
    with incomplete_record(name):
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise TypeError(CONTRACT_SET_FIELD)
        structures, meanings = _pins([row for row in rows if isinstance(row, dict)], name)
    changed = contract_stamp.changed_contracts(structures, meanings)
    if changed:
        listed: list[JsonValue] = list(changed)
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            f"{carrier} was written under another development contract set",
            {"record": name, "changed_contracts": listed, "remedy": remedy},
        )


def _pins(rows: list[Mapping[str, JsonValue]], name: str) -> tuple[dict[str, str], dict[str, str]]:
    names = [str(row["contract"]) for row in rows]
    if names != sorted(set(names)):
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            f"{name}: its contract set is not in contract order or repeats a contract",
            {"record": name},
        )
    structures = {str(row["contract"]): str(row["structure"]) for row in rows}
    meanings = {str(row["contract"]): str(row["meaning"]) for row in rows}
    return structures, meanings
