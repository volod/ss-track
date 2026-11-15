"""A sealed record format."""

from dataclasses import dataclass

from ss_track.core.refusal import JsonValue
from ss_track.schema.registry.contract import KIND_FIELD, VERSION_FIELD


@dataclass(frozen=True, slots=True)
class RecordFormat:
    """One kind of sealed record and the major this code reads and writes: their one statement."""

    kind: str
    major: int

    def stamp(self) -> dict[str, JsonValue]:
        """Return the fields every record of this format opens with, as its writer writes them."""
        return {KIND_FIELD: self.kind, VERSION_FIELD: self.major}
