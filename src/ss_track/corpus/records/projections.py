"""Comparison projections: the facts a later version or an amendment report reads.

Lineage reads a corpus version's source hashes, groups and splits. A later video stream also
carries `content_sha256`, the file hash, when its identity is not that hash. The amendment report reads each
stream's source-record pin. The shared-frame rule reads a bundle's frame hashes. A projection yields
only those, from a record as it was written, and stays for as long as records of its major may exist:
a record's disposition decides whether it may serve as evidence, never whether a successor is compared
with it. Corpus major 1 held no group or split, so it has no projection and a successor reports it as
not compared. Bundle major 1 has none either: only a corpus version of major 1 staged one.
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.corpus.records.kinds import CORPUS_MANIFEST_KIND, FRAME_BUNDLE_KIND

OTHER_SCHEMA = "other_schema"
SUPERSEDES_FIELD = "supersedes"
PLACEMENT_KEYS = ("stream_id", "source_sha256", "group_id", "split")
SOURCE_PIN = "source_manifest_sha256"
_STREAM_KEYS = (*PLACEMENT_KEYS, SOURCE_PIN)
FRAMES_FIELD = "frames"

type Projection = Callable[[Mapping[str, Any]], dict[str, JsonValue]]


@dataclass(frozen=True, slots=True)
class NotCompared:
    """A declared predecessor, or some of its streams, that a comparison cannot speak for."""

    corpus_id: str
    reason: str
    stream_ids: tuple[str, ...] = ()

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {
            "corpus_id": self.corpus_id,
            "reason": self.reason,
            "stream_ids": list(self.stream_ids),
        }


@dataclass(frozen=True, slots=True)
class Unprojected:
    """An intact corpus version whose major keeps no projection: its seal, and nothing to compare."""

    corpus_id: str
    manifest_sha256: str

    def gap(self) -> NotCompared:
        """Name it as not compared, under the reason that its format alone holds no comparison."""
        return NotCompared(self.corpus_id, OTHER_SCHEMA)


def _corpus(record: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Project a corpus version's placement and the source record each stream pins."""
    projected: dict[str, JsonValue] = {
        key: record[key] for key in ("kind", "schema_version", SEAL_FIELD, "corpus_id")
    }
    projected["decode_policy_sha256"] = record["decode_policy_sha256"]
    projected["streams"] = [_project_stream(stream) for stream in record["streams"]]
    if SUPERSEDES_FIELD in record:
        projected[SUPERSEDES_FIELD] = record[SUPERSEDES_FIELD]
    return projected


def _project_stream(stream: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Project one stream. A later camera keeps the file hash beside its own identity."""
    projected = {key: stream[key] for key in _STREAM_KEYS}
    content = stream.get("content_sha256")
    if isinstance(content, str):
        projected["content_sha256"] = content
    return projected


def _bundle(record: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Project a bundle's frame hashes, in presentation order, with the pins that place it."""
    projected: dict[str, JsonValue] = {
        key: record[key]
        for key in (
            "kind",
            "schema_version",
            SEAL_FIELD,
            "stream_id",
            "corpus_manifest_sha256",
            "bundle_sha256",
        )
    }
    projected[FRAMES_FIELD] = [
        [entry["frame_index"], entry["sha256"]] for entry in record["identity"]["frames"]
    ]
    return projected


def bundle_frames(projected: Mapping[str, Any]) -> Iterator[tuple[int, str]]:
    """Yield a projected bundle's `(frame_index, sha256)` pairs, in presentation order."""
    return ((frame_index, sha256) for frame_index, sha256 in projected[FRAMES_FIELD])


def installed_projections() -> Mapping[tuple[str, int], Projection]:
    """Return the projection of every major whose records may still be compared."""
    return INSTALLED_PROJECTIONS


INSTALLED_PROJECTIONS: dict[tuple[str, int], Projection] = {
    (CORPUS_MANIFEST_KIND, 2): _corpus,
    (CORPUS_MANIFEST_KIND, 3): _corpus,
    (FRAME_BUNDLE_KIND, 2): _bundle,
    (FRAME_BUNDLE_KIND, 3): _bundle,
}
