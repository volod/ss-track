"""Other built versions on one data root that place a source elsewhere.

Independent work may reuse a recording, so this listing refuses nothing. It reads every version
directory directly under the corpus directory through `read_comparable` and names one it cannot
read, or one whose major keeps no projection. A version directory that cannot be read is named the
same way. Declared predecessors stay with the split refusal and are not listed again. An amendment
report walks the same manifests.
"""

import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.projections import OTHER_SCHEMA
from ss_track.corpus.records.sealed import Comparable, read_comparable
from ss_track.corpus.sources.importer import MANIFEST_NAME
from ss_track.corpus.versions.lineage import sources_placed_elsewhere
from ss_track.corpus.versions.predecessors import Predecessor, predecessor_identity

UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class ScannedManifest:
    """One corpus manifest on a data root, or the failure to read it."""

    corpus_id: str
    path: Path
    comparable: Comparable | None


@dataclass(frozen=True, slots=True)
class UnreadCorpus:
    """A manifest the listing could not compare."""

    corpus_id: str
    reason: str

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {"corpus_id": self.corpus_id, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class UnlinkedVersions:
    """What a build found outside its declared chain. Empty means nothing to report."""

    placements: tuple[Mapping[str, JsonValue], ...]
    not_compared: tuple[UnreadCorpus, ...]
    scan: str | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form. Each list is absent when it is empty."""
        record: dict[str, JsonValue] = {}
        if self.placements:
            record["placements"] = [dict(item) for item in self.placements]
        if self.not_compared:
            record["not_compared"] = [gap.to_record() for gap in self.not_compared]
        if self.scan is not None:
            record["scan"] = self.scan
        return record

    def when_present(self) -> dict[str, JsonValue]:
        """Return the `unlinked` field, or nothing when this report is empty.

        The field is not sealed. It describes the data root at build time, including a repeat
        whose corpus bytes did not change.
        """
        listed = self.to_record()
        if not listed:
            return {}
        return {"unlinked": listed}


def compared_record(scanned: ScannedManifest) -> dict[str, JsonValue] | UnreadCorpus:
    """Return this manifest's projection, or why it cannot be compared."""
    comparable = scanned.comparable
    if comparable is None or comparable.projected is None:
        reason = UNREADABLE if comparable is None else OTHER_SCHEMA
        return UnreadCorpus(scanned.corpus_id, reason)
    return comparable.projected


def scan_corpus_manifests(
    root: Path, record_format: RecordFormat, *, name_missing: bool = False
) -> tuple[ScannedManifest, ...]:
    """Read one manifest per version directory, in directory-name order.

    A manifest or version directory that cannot be read is returned with no comparable record, so
    a caller can name it instead of treating that version as absent. The walk stops at one
    directory level: bundle manifests live further down and are not corpus versions. A name with a
    leading dot is not a version. A directory with no manifest is not a version unless
    `name_missing` is set, in which case it is returned with no comparable record. Raises OSError
    when `root` itself cannot be listed.
    """
    if not root.is_dir():
        return ()
    found: list[ScannedManifest] = []
    for path in _version_directories(root):
        manifest = path / MANIFEST_NAME
        try:
            comparable = _read_manifest(manifest, record_format)
        except FileNotFoundError:
            if not name_missing:
                continue
            comparable = None
        except OSError:
            comparable = None
        found.append(ScannedManifest(path.name, manifest, comparable))
    return tuple(found)


def _version_directories(root: Path) -> tuple[Path, ...]:
    """Return child directories in name order.

    A child that cannot be stat'd is included, so the caller names it instead of skipping a
    version whose manifest it cannot see. Raises OSError when `root` cannot be listed.
    """
    chosen: list[Path] = []
    for path in root.iterdir():
        if path.name.startswith("."):
            continue
        try:
            is_directory = stat.S_ISDIR(path.stat().st_mode)
        except OSError:
            is_directory = True
        if is_directory:
            chosen.append(path)
    return tuple(sorted(chosen, key=lambda item: item.name))


def _read_manifest(manifest: Path, record_format: RecordFormat) -> Comparable | None:
    """Return the comparable record, or None when the manifest cannot be read.

    Raises FileNotFoundError when the directory holds no manifest, and OSError when the manifest
    cannot be stat'd.
    """
    manifest.stat()
    try:
        return read_comparable(manifest, record_format)
    except (CorpusRefusal, OSError):
        return None


def report_unlinked(
    corpus_id: str,
    streams: Sequence[Mapping[str, Any]],
    predecessors: Sequence[Predecessor],
    corpus_root: Path,
    record_format: RecordFormat,
) -> UnlinkedVersions:
    """List versions that place one of `streams` elsewhere, and manifests that were not compared.

    `corpus_id` is the version being built. It and every declared predecessor are left out.
    Placements are ordered by source hash, then by the other version's directory name. Manifests
    that were not compared are ordered by that name. A corpus directory that cannot be listed is
    reported as `scan` instead of raising from the walk.
    """
    try:
        manifests = scan_corpus_manifests(corpus_root, record_format)
    except OSError:
        return UnlinkedVersions((), (), UNREADABLE)
    excluded = {corpus_id, *(predecessor_identity(item)[0] for item in predecessors)}
    placements: list[Mapping[str, JsonValue]] = []
    unread: list[UnreadCorpus] = []
    for scanned in manifests:
        if scanned.corpus_id in excluded:
            continue
        ready = compared_record(scanned)
        if isinstance(ready, UnreadCorpus):
            unread.append(ready)
            continue
        named = dict(ready)
        named["corpus_id"] = scanned.corpus_id
        placements.extend(sources_placed_elsewhere(corpus_id, streams, named))
    ordered = tuple(sorted(placements, key=_placement_order))
    return UnlinkedVersions(ordered, tuple(sorted(unread, key=lambda gap: gap.corpus_id)))


def _placement_order(item: Mapping[str, JsonValue]) -> tuple[str, str]:
    other = item["from"]
    name = other["corpus_id"] if isinstance(other, dict) else ""
    return str(item["source_sha256"]), str(name)
