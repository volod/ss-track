"""`ss-track corpus build`: bind imported sources into one immutable, hashed corpus version."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.cases.recipes import case_records
from ss_track.corpus.declarations.declaration import CorpusDeclaration, load_corpus_declaration
from ss_track.corpus.decoding.decode_policy import (
    DecodePolicy,
    current_decode_policy,
    require_policy,
)
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.sources.terms import evaluation_date, require_retention
from ss_track.corpus.storage.layout import corpus_manifest_path
from ss_track.corpus.versions.capture_counts import (
    CaptureEncounterCounts,
    count_capture_encounters,
)
from ss_track.corpus.versions.grouping import (
    SplitSummary,
    require_derived_frames,
    require_one_membership,
    require_scenario_rights,
    require_separate_sources,
    summarize_splits,
)
from ss_track.corpus.versions.lineage import (
    Lineage,
    lineage_record,
    require_same_places,
    trace_lineage,
)
from ss_track.corpus.versions.manifests import built_manifest_path, load_predecessor
from ss_track.corpus.versions.near_duplicate_scan import fingerprint_manifest
from ss_track.corpus.versions.near_duplicates import NearDuplicates, report_near_duplicates
from ss_track.corpus.versions.placement import stream_record
from ss_track.corpus.versions.predecessors import link_field, read_predecessors
from ss_track.corpus.versions.unlinked import UnlinkedVersions, report_unlinked


@dataclass(frozen=True, slots=True)
class BuildResult:
    """Outcome of an accepted corpus build."""

    status: str
    corpus_id: str
    manifest_sha256: str
    manifest_path: Path
    stream_count: int
    generated_case_count: int
    splits: dict[str, SplitSummary]
    capture_encounters: CaptureEncounterCounts
    lineage: Lineage | None
    unlinked: UnlinkedVersions
    near_duplicates: NearDuplicates

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        record: dict[str, JsonValue] = {
            "status": self.status,
            "corpus_id": self.corpus_id,
            "manifest_sha256": self.manifest_sha256,
            "manifest_path": str(self.manifest_path),
            "stream_count": self.stream_count,
            "generated_case_count": self.generated_case_count,
            "splits": {name: summary.to_record() for name, summary in self.splits.items()},
            "capture_encounters": self.capture_encounters.to_record(),
            "lineage": lineage_record(self.lineage),
        }
        record.update(self.unlinked.when_present())
        record.update(self.near_duplicates.when_present())
        return record


def build_corpus(
    declaration_path: Path, data_root: Path, *, today: date | None = None
) -> BuildResult:
    """Verify every declared source again, then write the corpus version."""
    checked_on = evaluation_date(today)
    declaration = load_corpus_declaration(declaration_path)
    policy = current_decode_policy()
    policy_sha256 = policy.sha256()
    require_policy(declaration.decode_policy_sha256, policy_sha256, "corpus declaration")
    require_one_membership(declaration)
    predecessors = read_predecessors(
        declaration.supersedes, lambda corpus_id: load_predecessor(corpus_id, data_root)
    )
    placed = sorted(
        (
            stream_record(group, encounter, stream, data_root, policy_sha256)
            for group, encounter, stream in declaration.members()
        ),
        key=lambda item: str(item[0]["stream_id"]),
    )
    streams = [record for record, _judgments in placed]
    for stream in streams:
        require_retention(stream, checked_on)
    require_derived_frames(streams, declaration)
    require_separate_sources(streams)
    require_scenario_rights(streams, declaration.scenario_rights)
    require_same_places(declaration.corpus_id, streams, predecessors)
    unlinked = report_unlinked(
        declaration.corpus_id, streams, predecessors, data_root, CORPUS_MANIFEST
    )
    cases = case_records(list(declaration.recipes()), streams)
    near_duplicates = report_near_duplicates(
        declaration.corpus_id,
        streams,
        predecessors,
        data_root,
        lambda corpus_id: fingerprint_manifest(
            built_manifest_path(corpus_id, data_root), CORPUS_MANIFEST
        ),
        CORPUS_MANIFEST,
    )
    body = _corpus_body(declaration, policy, streams, cases)
    sealed = seal(body | link_field(predecessors))
    target = corpus_manifest_path(data_root, declaration.corpus_id)
    status = _commit(target, sealed)
    return BuildResult(
        status=status,
        corpus_id=declaration.corpus_id,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=target,
        stream_count=len(streams),
        generated_case_count=len(cases),
        splits=summarize_splits(streams, cases),
        capture_encounters=count_capture_encounters(
            [(str(record["encounter_id"]), judgments) for record, judgments in placed]
        ),
        lineage=trace_lineage(streams, predecessors),
        unlinked=unlinked,
        near_duplicates=near_duplicates,
    )


def _corpus_body(
    declaration: CorpusDeclaration,
    policy: DecodePolicy,
    streams: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, JsonValue]:
    rights = declaration.scenario_rights
    return {
        **CORPUS_MANIFEST.stamp(),
        "corpus_id": declaration.corpus_id,
        **policy.record_fields(),
        "scenario_rights": {"sharing": rights.sharing, "max_sensitivity": rights.max_sensitivity},
        "streams": list(streams),
        "generated_cases": list(cases),
    }


def _commit(target: Path, sealed: dict[str, JsonValue]) -> str:
    """A corpus version is immutable: a changed one needs a new identifier."""
    if not target.exists():
        write_sealed(target, sealed)
        return "built"
    existing = read_sealed(target, CORPUS_MANIFEST)
    if existing != sealed:
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this corpus_id already exists with different content",
            {
                "existing_manifest_sha256": existing[SEAL_FIELD],
                "new_manifest_sha256": sealed[SEAL_FIELD],
            },
        )
    return "unchanged"
