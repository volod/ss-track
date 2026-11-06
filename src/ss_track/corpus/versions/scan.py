"""Every corpus version on one data root, read for a listing that refuses nothing.

The unlinked-version listing, the amendment impact and the near-duplicate scan each read every
version directory directly under the corpus directory, through `read_comparable`, and name one
they could not compare instead of treating it as absent. This module is that one walk.
"""

import stat
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.projections import OTHER_SCHEMA
from ss_track.corpus.records.sealed import Comparable, read_comparable
from ss_track.corpus.storage.layout import MANIFEST_NAME, corpus_root

UNREADABLE = "unreadable"
_HIDDEN_PREFIX = "."

type Projected = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class UnreadCorpus:
    """A version directory the walk could not compare, and why."""

    corpus_id: str
    reason: str

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {"corpus_id": self.corpus_id, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class VersionScan:
    """Each version the walk compared, by name, and each it could not, in name order.

    `scan` is set when the corpus directory itself could not be listed, and both lists are then
    empty.
    """

    compared: tuple[tuple[str, Projected], ...]
    not_compared: tuple[UnreadCorpus, ...]
    scan: str | None = None


def scan_versions(
    data_root: Path,
    record_format: RecordFormat,
    *,
    excluded: Collection[str] = (),
    name_missing: bool = False,
) -> VersionScan:
    """Read one manifest per version directory through its major's projection.

    A manifest or directory that cannot be read, and a major that keeps no projection, are named.
    The walk stops at one level: bundle manifests live further down and are not versions. A name
    with a leading dot is not a version. A directory with no manifest is not a version unless
    `name_missing` is set. `excluded` names versions the caller already reads another way.
    """
    try:
        directories = _version_directories(corpus_root(data_root))
    except OSError:
        return VersionScan((), (), UNREADABLE)
    compared: list[tuple[str, Projected]] = []
    unread: list[UnreadCorpus] = []
    for path in directories:
        found = None if path.name in excluded else _compare(path, record_format, name_missing)
        if isinstance(found, UnreadCorpus):
            unread.append(found)
        elif found is not None:
            compared.append((path.name, found))
    return VersionScan(tuple(compared), tuple(unread))


def _compare(
    directory: Path, record_format: RecordFormat, name_missing: bool
) -> Projected | UnreadCorpus | None:
    """Return one version's projection, why it was not compared, or None when it is no version."""
    try:
        comparable = _read_manifest(directory / MANIFEST_NAME, record_format)
    except FileNotFoundError:
        return UnreadCorpus(directory.name, UNREADABLE) if name_missing else None
    if comparable is None:
        return UnreadCorpus(directory.name, UNREADABLE)
    if comparable.projected is None:
        return UnreadCorpus(directory.name, OTHER_SCHEMA)
    return comparable.projected


def scan_fields(not_compared: Collection[Any], scan: str | None) -> dict[str, JsonValue]:
    """Return a listing's `not_compared` and `scan` fields, each absent when there is nothing."""
    fields: dict[str, JsonValue] = {}
    if not_compared:
        fields["not_compared"] = [gap.to_record() for gap in not_compared]
    if scan is not None:
        fields["scan"] = scan
    return fields


def _version_directories(root: Path) -> tuple[Path, ...]:
    """Return child directories in name order.

    A child that cannot be stat'd is included, so the caller names it instead of skipping a
    version whose manifest it cannot see. Raises OSError when `root` cannot be listed. A data root
    with no corpus directory has no versions.
    """
    if not root.is_dir():
        return ()
    chosen: list[Path] = []
    for path in root.iterdir():
        if path.name.startswith(_HIDDEN_PREFIX):
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

    Raises FileNotFoundError when the directory holds no manifest.
    """
    try:
        manifest.stat()
    except FileNotFoundError:
        raise
    except OSError:
        return None
    try:
        return read_comparable(manifest, record_format)
    except (CorpusRefusal, OSError):
        return None
