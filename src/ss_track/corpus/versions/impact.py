"""Corpus versions on one data root that pin a replaced source record.

An amendment or a redecode refuses nothing and removes nothing. The listing names a manifest it
cannot read, a version directory it cannot read, and a major that keeps no projection. It does not
refuse the replacement, which is already recorded. Versions on another data root are out of reach.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import JsonValue
from ss_track.corpus.bundles.frames import frames_root
from ss_track.corpus.records.projections import SOURCE_PIN
from ss_track.corpus.versions.builder import CORPUS_DIRECTORY, CORPUS_MANIFEST
from ss_track.corpus.versions.unlinked import (
    UNREADABLE,
    UnreadCorpus,
    compared_record,
    scan_corpus_manifests,
)


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
        if self.not_compared:
            record["not_compared"] = [gap.to_record() for gap in self.not_compared]
        if self.scan is not None:
            record["scan"] = self.scan
        return record


def report_amendment_impact(data_root: Path, replaced_manifest_sha256: str) -> AmendmentImpact:
    """List versions whose streams pin `replaced_manifest_sha256`, without refusing the replacement.

    Versions are ordered by directory name, and so are manifests that were not compared. A version
    is listed once, however many of its streams pin the record. The frames directory is that
    version's bundle directory, whether or not it currently holds files.
    """
    root = data_root / CORPUS_DIRECTORY
    try:
        scanned = scan_corpus_manifests(root, CORPUS_MANIFEST)
    except OSError:
        return AmendmentImpact((), (), UNREADABLE)
    versions: list[PinnedVersion] = []
    unread: list[UnreadCorpus] = []
    for item in scanned:
        ready = compared_record(item)
        if isinstance(ready, UnreadCorpus):
            unread.append(ready)
            continue
        if _pins(ready, replaced_manifest_sha256):
            versions.append(PinnedVersion(item.corpus_id, frames_root(data_root, item.corpus_id)))
    return AmendmentImpact(
        tuple(sorted(versions, key=lambda version: version.corpus_id)),
        tuple(sorted(unread, key=lambda gap: gap.corpus_id)),
    )


def _pins(projected: Mapping[str, JsonValue], seal: str) -> bool:
    """Return whether any projected stream pins `seal`."""
    streams = projected.get("streams")
    if not isinstance(streams, list):
        return False
    return any(isinstance(stream, dict) and stream.get(SOURCE_PIN) == seal for stream in streams)
