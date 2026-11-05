"""Each sealed record format: the kind it stamps and the one major this code reads and writes.

They sit apart from the writers so that the read path, the writers and the refusals name a format
by one value, and a format change has one place to go.
"""

from dataclasses import dataclass

from ss_track.core.refusal import JsonValue
from ss_track.schema.registry.contract import KIND_FIELD, VERSION_FIELD

SOURCE_MANIFEST_KIND = "ss-track.source-manifest"
CORPUS_MANIFEST_KIND = "ss-track.corpus-manifest"
FRAME_BUNDLE_KIND = "ss-track.frame-bundle"
FRAME_SET_KIND = "ss-track.frame-set"
STAGED_HASHES_KIND = "ss-track.staged-hashes"
HASH_COMPARISON_KIND = "ss-track.hash-comparison"


@dataclass(frozen=True, slots=True)
class RecordFormat:
    """One kind of sealed record and the major this code reads and writes: their one statement."""

    kind: str
    major: int

    def stamp(self) -> dict[str, JsonValue]:
        """Return the fields every record of this format opens with, as its writer writes them."""
        return {KIND_FIELD: self.kind, VERSION_FIELD: self.major}
