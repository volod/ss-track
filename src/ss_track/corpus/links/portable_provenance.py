"""Bind a development handoff to the contract set its exporting data root was written under.

A development record of an edited contract keeps `schema_version: 1`, so matching data hashes do not
prove that two roots read the carried records the same way (spec section 17.7). The exporter pins
every record and shared contract's structure and meaning; a receiver refuses any difference before
it writes a local record or review state. In the released stage the pins are null and a record's
major identifies its contract instead.
"""

from collections.abc import Mapping

from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.read_refusals import incomplete_record
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

CONTRACT_SET_FIELD = "contract_set"
HANDOFF_REMEDY = (
    "export and open the handoff with ss-track versions that install the same contract set: "
    "regenerate the exporting data root under the receiver's contract set and export again, or open "
    "it with the ss-track that exported it (spec section 17.7)"
)


def exported_contract_set() -> list[JsonValue] | None:
    """Return the installed record and shared pins in contract order, or None after release."""
    structures = contract_stamp.installed_fingerprints()
    meanings = contract_stamp.installed_meanings()
    if structures is None or meanings is None:
        return None
    return [
        {"contract": name, "structure": structures[name], "meaning": meanings[name]}
        for name in sorted(structures)
    ]


def _pins(rows: list[Mapping[str, JsonValue]]) -> tuple[dict[str, str], dict[str, str]]:
    names = [str(row["contract"]) for row in rows]
    if names != sorted(set(names)):
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "handoff contract set is not in contract order or repeats a contract",
        )
    structures = {str(row["contract"]): str(row["structure"]) for row in rows}
    meanings = {str(row["contract"]): str(row["meaning"]) for row in rows}
    return structures, meanings


def require_matching_contract_set(manifest: Mapping[str, JsonValue]) -> None:
    """Refuse a development handoff whose contract pins are absent or differ from this install."""
    if contract_stamp.installed_fingerprints() is None:
        return
    rows = manifest.get(CONTRACT_SET_FIELD)
    if rows is None:
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            "the review handoff does not state the development contract set it was exported under",
            {"field": CONTRACT_SET_FIELD, "remedy": HANDOFF_REMEDY},
        )
    with incomplete_record("manifest.json"):
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise TypeError(CONTRACT_SET_FIELD)
        structures, meanings = _pins([row for row in rows if isinstance(row, dict)])
    changed = contract_stamp.changed_contracts(structures, meanings)
    if changed:
        listed: list[JsonValue] = list(changed)
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            "the review handoff was exported under another development contract set",
            {"changed_contracts": listed, "remedy": HANDOFF_REMEDY},
        )
