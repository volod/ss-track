"""Corpus versions on one data root that pin a replaced source record.

An amendment or a redecode refuses nothing and removes nothing. The listing names a manifest it
cannot read, a version directory it cannot read, and a major that keeps no projection. It does not
refuse the replacement, which is already recorded. Versions on another data root are out of reach.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import JsonValue
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.records.projections import SOURCE_PIN
from ss_track.corpus.storage.layout import frames_root
from ss_track.corpus.versions.scan import UnreadCorpus, scan_fields, scan_versions


@dataclass(frozen=True, slots=True)
class PinnedVersion:
    """One corpus version whose streams pin a replaced source record."""

    corpus_id: str
    frames_directory: Path

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {"corpus_id": self.corpus_id, "frames_directory": str(self.frames_directory)}


@dataclass(frozen=True, slots=True)
class AmendmentImpact:
    """Versions that pin a replaced record, and manifests that were not compared.

    Empty means nothing to report. `scan` is set when the corpus directory itself could not be
    listed, and then both lists are empty.
    """

    versions: tuple[PinnedVersion, ...]
    not_compared: tuple[UnreadCorpus, ...]
    scan: str | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form. Each list is absent when it is empty."""
        record: dict[str, JsonValue] = {}
        if self.versions:
            record["versions"] = [item.to_record() for item in self.versions]
        return record | scan_fields(self.not_compared, self.scan)


def report_amendment_impact(data_root: Path, replaced_manifest_sha256: str) -> AmendmentImpact:
    """List versions whose streams pin `replaced_manifest_sha256`, without refusing the replacement.

    Versions are ordered by directory name, and so are manifests that were not compared. A version
    is listed once, however many of its streams pin the record. The frames directory is that
    version's bundle directory, whether or not it currently holds files.
    """
    found = scan_versions(data_root, CORPUS_MANIFEST)
    versions = tuple(
        PinnedVersion(corpus_id, frames_root(data_root, corpus_id))
        for corpus_id, projected in found.compared
        if _pins(projected, replaced_manifest_sha256)
    )
    return AmendmentImpact(versions, found.not_compared, found.scan)


def _pins(projected: Mapping[str, JsonValue], seal: str) -> bool:
    """Return whether any projected stream pins `seal`."""
    streams = projected.get("streams")
    if not isinstance(streams, list):
        return False
    return any(isinstance(stream, dict) and stream.get(SOURCE_PIN) == seal for stream in streams)
