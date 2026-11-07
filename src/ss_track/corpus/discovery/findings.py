"""One broken rule of a discovery record, and the refusal that reports every broken rule at once.

The contracts state these rules in words under `x-rules`, because JSON Schema cannot compare two
values. A finding names the rule by that key, the record and the JSON pointer of the value, so an
operator can find it without this code.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

RUN_RECORD = "run"
INVENTORY_PREFIX = "inventories/"


@dataclass(frozen=True, slots=True, order=True)
class Finding:
    """One rule a record breaks."""

    record: str  # `run`, or `inventories/<stream_id>`
    pointer: str  # JSON pointer of the value inside that record
    rule: str  # the `x-rules` key of the contract that states it
    message: str

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {
            "record": self.record,
            "pointer": self.pointer,
            "rule": self.rule,
            "message": self.message,
        }


def inventory_label(stream_id: str) -> str:
    """Name a stream's inventory as a finding states it."""
    return f"{INVENTORY_PREFIX}{stream_id}"


def require_no_findings(findings: Sequence[Finding], run_id: str) -> None:
    """Refuse discovery records that break any rule, naming every broken rule in a stable order."""
    if findings:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID,
            "discovery records break their contract rules",
            {"run_id": run_id, "findings": [item.to_record() for item in sorted(findings)]},
        )
