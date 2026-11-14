"""Read a reviewer's link decisions: which pairs of recordings are related, and which are not.

A decision names two source identities, never a corpus version, so it carries over to every version
that holds both recordings. Whether two recordings are independent is the reviewer's judgment: a
score can only ask the question.
"""

from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.schema.validation.enforce import read_declaration

DECISIONS_CONTRACT = "declaration/link-decisions"
DECISIONS_SCHEMA_VERSION = 1
RELATED = "related"
UNRELATED = "unrelated"

type SourcePair = tuple[str, str]


def source_pair(first: str, second: str) -> SourcePair:
    """Return two source identities in ascending order: the one key of a pair."""
    return (first, second) if first <= second else (second, first)


@dataclass(frozen=True, slots=True)
class Decision:
    """One reviewer decision on one pair of recordings."""

    sources: SourcePair
    decision: str
    note: str | None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the form a link record copies, so the record alone shows what was decided."""
        record: dict[str, JsonValue] = {"decision": self.decision}
        if self.note is not None:
            record["note"] = self.note
        return record


@dataclass(frozen=True, slots=True)
class Decisions:
    """Every decision of one review, keyed by pair, and who made them."""

    reviewer: str
    by_pair: dict[SourcePair, Decision]


def read_decisions(path: Path) -> Decisions:
    """Read one decisions file under its contract, refusing a pair decided twice or with itself."""
    fields = Fields(read_declaration(path, DECISIONS_CONTRACT, DECISIONS_SCHEMA_VERSION), path.name)
    by_pair: dict[SourcePair, Decision] = {}
    for position, raw in enumerate(fields.items("decisions")):
        entry = Fields(raw, f"{path.name}.decisions[{position}]")
        first, second = (str(source) for source in entry.items("sources"))
        if first == second:
            raise invalid(f"{entry.where}.sources names one source twice")
        pair = source_pair(first, second)
        if pair in by_pair:
            raise invalid(f"{entry.where} decides a pair of sources already decided")
        by_pair[pair] = Decision(pair, entry.text("decision"), entry.optional_text("note"))
    return Decisions(fields.text("reviewer"), by_pair)
