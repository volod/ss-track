"""Other built versions on one data root that place a source elsewhere.

Independent work may reuse a recording, so this listing refuses nothing. It reads every version on
the data root through the walk in `corpus.versions.scan` and names one it cannot compare. Declared
predecessors stay with the split refusal and are not listed again.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.versions.lineage import sources_placed_elsewhere
from ss_track.corpus.versions.predecessors import Predecessor, predecessor_name
from ss_track.corpus.versions.scan import UnreadCorpus, scan_fields, scan_versions


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
        return record | scan_fields(self.not_compared, self.scan)

    def when_present(self) -> dict[str, JsonValue]:
        """Return the `unlinked` field, or nothing when this report is empty.

        The field is not sealed. It describes the data root at build time, including a repeat
        whose corpus bytes did not change.
        """
        listed = self.to_record()
        if not listed:
            return {}
        return {"unlinked": listed}


def report_unlinked(
    corpus_id: str,
    streams: Sequence[Mapping[str, Any]],
    predecessors: Sequence[Predecessor],
    data_root: Path,
    record_format: RecordFormat,
) -> UnlinkedVersions:
    """List versions that place one of `streams` elsewhere, and manifests that were not compared.

    `corpus_id` is the version being built. It and every declared predecessor are left out.
    Placements are ordered by source hash, then by the other version's directory name. Manifests
    that were not compared are ordered by that name. A corpus directory that cannot be listed is
    reported as `scan` instead of raising from the walk.
    """
    excluded = {corpus_id, *(predecessor_name(item) for item in predecessors)}
    found = scan_versions(data_root, record_format, excluded=excluded)
    placements: list[Mapping[str, JsonValue]] = []
    for other_id, projected in found.compared:
        named = projected | {"corpus_id": other_id}
        placements.extend(sources_placed_elsewhere(corpus_id, streams, named))
    ordered = tuple(sorted(placements, key=_placement_order))
    return UnlinkedVersions(ordered, found.not_compared, found.scan)


def _placement_order(item: Mapping[str, JsonValue]) -> tuple[str, str]:
    other = item["from"]
    name = other["corpus_id"] if isinstance(other, dict) else ""
    return str(item["source_sha256"]), str(name)
