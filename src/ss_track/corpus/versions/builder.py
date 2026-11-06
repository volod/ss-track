"""`ss-track corpus build`: bind imported sources into one immutable, hashed corpus version."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.cases.recipes import case_records
from ss_track.corpus.declarations.declaration import (
    CorpusDeclaration,
    EncounterDeclaration,
    GroupDeclaration,
    StreamDeclaration,
    load_corpus_declaration,
)
from ss_track.corpus.decoding.decode_policy import (
    DecodePolicy,
    current_decode_policy,
    require_policy,
)
from ss_track.corpus.decoding.streams import recorded_video_stream_index
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.records.read_refusals import incomplete_record
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.sources.identity import recorded_content_sha256, source_identity
from ss_track.corpus.sources.stored import load_verified_source
from ss_track.corpus.sources.terms import evaluation_date, require_retention
from ss_track.corpus.storage.layout import MANIFEST_NAME, corpus_manifest_path
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
from ss_track.corpus.versions.predecessors import link_field, read_predecessors
from ss_track.corpus.versions.unlinked import UnlinkedVersions, report_unlinked

CAMERA_MODALITY = "camera"


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
    streams = sorted(
        (
            _stream_record(group, encounter, stream, data_root, policy_sha256)
            for group, encounter, stream in declaration.members()
        ),
        key=lambda record: str(record["stream_id"]),
    )
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


def _resolve_selection(stream: StreamDeclaration, frame_count: int) -> dict[str, JsonValue]:
    """Return the frame window, which must lie inside the decoded sequence."""
    selection = stream.selection
    if selection is None:
        return {"start_frame": 0, "end_frame": frame_count}
    if selection.end_frame > frame_count:
        raise CorpusRefusal(
            RefusalCode.SELECTION_OUT_OF_RANGE,
            "selection runs past the end of the sequence",
            {
                "stream_id": stream.stream_id,
                "start_frame": selection.start_frame,
                "end_frame": selection.end_frame,
                "frame_count": frame_count,
            },
        )
    return {"start_frame": selection.start_frame, "end_frame": selection.end_frame}


def _stream_record(
    group: GroupDeclaration,
    encounter: EncounterDeclaration,
    stream: StreamDeclaration,
    data_root: Path,
    policy_sha256: str,
) -> dict[str, JsonValue]:
    verified = load_verified_source(stream.source_sha256, data_root)
    manifest = verified.record
    require_policy(
        manifest["decode_policy_sha256"], policy_sha256, f"source {stream.source_sha256}"
    )
    media = verified.sequence
    with incomplete_record(MANIFEST_NAME):
        record = _placed_stream(group, encounter, stream, manifest, media)
    content = recorded_content_sha256(manifest)
    index = recorded_video_stream_index(media)
    if content != stream.source_sha256 and source_identity(content, index) == stream.source_sha256:
        record["content_sha256"] = content
    return record


def _placed_stream(
    group: GroupDeclaration,
    encounter: EncounterDeclaration,
    stream: StreamDeclaration,
    manifest: Mapping[str, JsonValue],
    media: Mapping[str, Any],
) -> dict[str, JsonValue]:
    """State one declared stream with the facts its source record holds."""
    frame_count = media["frame_count"]
    if not isinstance(frame_count, int):
        raise TypeError("frame_count")
    return {
        "stream_id": stream.stream_id,
        "modality": CAMERA_MODALITY,
        "encounter_id": encounter.encounter_id,
        "group_id": group.group_id,
        "split": group.split,
        "source_sha256": stream.source_sha256,
        "source_manifest_sha256": manifest[SEAL_FIELD],
        "selection": _resolve_selection(stream, frame_count),
        "frame_count": frame_count,
        "width": media["decoded_width"],
        "height": media["decoded_height"],
        "timestamp_quality": media["timestamp_quality"],
        "completeness_checks": media["completeness_checks"],
        "rights": manifest["rights"],
        "sensitivity": manifest["sensitivity"],
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
