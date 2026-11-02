"""`ss-track corpus build`: bind imported sources into one immutable, hashed corpus version."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ss_track.corpus.declaration import (
    CORPUS_SCHEMA_VERSION,
    CorpusDeclaration,
    EncounterDeclaration,
    GroupDeclaration,
    StreamDeclaration,
    load_corpus_declaration,
)
from ss_track.corpus.decode import current_decode_policy
from ss_track.corpus.fields import IDENTIFIER_PATTERN
from ss_track.corpus.grouping import (
    SplitSummary,
    require_derived_frames,
    require_one_membership,
    require_scenario_rights,
    require_separate_sources,
    summarize_splits,
)
from ss_track.corpus.importer import (
    MANIFEST_NAME,
    SOURCE_MANIFEST_KIND,
    decode_policy_sha256,
    source_directory,
)
from ss_track.corpus.importer import (
    SCHEMA_VERSION as SOURCE_SCHEMA_VERSION,
)
from ss_track.corpus.lineage import (
    Lineage,
    lineage_record,
    link_field,
    read_predecessors,
    require_same_places,
    trace_lineage,
)
from ss_track.corpus.recipes import case_records
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import (
    SEAL_FIELD,
    read_sealed,
    require_schema,
    seal,
    sha256_file,
    write_sealed,
)
from ss_track.corpus.terms import changed_terms, evaluation_date, require_retention

CORPUS_MANIFEST_KIND = "ss-track.corpus-manifest"
CORPUS_DIRECTORY = "corpus"
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

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": self.status,
            "corpus_id": self.corpus_id,
            "manifest_sha256": self.manifest_sha256,
            "manifest_path": str(self.manifest_path),
            "stream_count": self.stream_count,
            "generated_case_count": self.generated_case_count,
            "splits": {name: summary.to_record() for name, summary in self.splits.items()},
            "lineage": lineage_record(self.lineage),
        }


def load_corpus_manifest(corpus_id: str, data_root: Path) -> dict[str, JsonValue]:
    """Read one built corpus version, refusing an identifier that cannot name one."""
    path = data_root / CORPUS_DIRECTORY / corpus_id / MANIFEST_NAME
    if not IDENTIFIER_PATTERN.fullmatch(corpus_id) or not path.is_file():
        raise CorpusRefusal(
            RefusalCode.CORPUS_NOT_BUILT, "no such corpus version", {"corpus_id": corpus_id}
        )
    manifest = read_sealed(path, CORPUS_MANIFEST_KIND)
    require_schema(manifest, CORPUS_SCHEMA_VERSION, path)
    return manifest


def build_corpus(
    declaration_path: Path, data_root: Path, *, today: date | None = None
) -> BuildResult:
    """Verify every declared source again, then write the corpus version."""
    checked_on = evaluation_date(today)
    declaration = load_corpus_declaration(declaration_path)
    policy_record = current_decode_policy().as_record()
    policy_sha256 = decode_policy_sha256(policy_record)
    require_policy(declaration.decode_policy_sha256, policy_sha256, "corpus declaration")
    require_one_membership(declaration)
    predecessors = read_predecessors(
        declaration.supersedes, lambda corpus_id: load_corpus_manifest(corpus_id, data_root)
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
    cases = case_records(list(declaration.recipes()), streams)
    body = _corpus_body(declaration, policy_record, policy_sha256, streams, cases)
    sealed = seal(body | link_field(predecessors))
    target = data_root / CORPUS_DIRECTORY / declaration.corpus_id / MANIFEST_NAME
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
    )


def _corpus_body(
    declaration: CorpusDeclaration,
    policy_record: dict[str, JsonValue],
    policy_sha256: str,
    streams: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, JsonValue]:
    rights = declaration.scenario_rights
    return {
        "kind": CORPUS_MANIFEST_KIND,
        "schema_version": CORPUS_SCHEMA_VERSION,
        "corpus_id": declaration.corpus_id,
        "decode_policy": policy_record,
        "decode_policy_sha256": policy_sha256,
        "scenario_rights": {"sharing": rights.sharing, "max_sensitivity": rights.max_sensitivity},
        "streams": list(streams),
        "generated_cases": list(cases),
    }


def require_policy(found: JsonValue, expected: str, origin: str) -> None:
    """Refuse a source decoded under anything but the corpus's one canonical policy."""
    if found is not None and found != expected:
        raise CorpusRefusal(
            RefusalCode.DECODE_POLICY_MISMATCH,
            f"{origin} uses a different decode policy than the installed decoder",
            {"found_decode_policy_sha256": found, "installed_decode_policy_sha256": expected},
        )


def _load_source_record(source_sha256: str, data_root: Path) -> dict[str, JsonValue]:
    manifest_path = source_directory(data_root, source_sha256) / MANIFEST_NAME
    if not manifest_path.is_file():
        raise CorpusRefusal(
            RefusalCode.SOURCE_NOT_IMPORTED,
            "the corpus names a source that has not been imported",
            {"source_sha256": source_sha256},
        )
    manifest = read_sealed(manifest_path, SOURCE_MANIFEST_KIND)
    require_schema(manifest, SOURCE_SCHEMA_VERSION, manifest_path)
    return manifest


def require_source_record(stream: Mapping[str, Any], data_root: Path) -> None:
    """Refuse a stream whose source was re-imported, because the corpus states its old rights."""
    manifest = _load_source_record(stream["source_sha256"], data_root)
    if manifest[SEAL_FIELD] != stream["source_manifest_sha256"]:
        raise CorpusRefusal(
            RefusalCode.SOURCE_RECORD_CHANGED,
            "this source's record changed after the corpus was built; build a new corpus version",
            {
                "stream_id": stream["stream_id"],
                "source_sha256": stream["source_sha256"],
                "corpus_source_manifest_sha256": stream["source_manifest_sha256"],
                "source_manifest_sha256": manifest[SEAL_FIELD],
                "changed_terms": list(changed_terms(stream, manifest)),
            },
        )


def load_verified_source(source_sha256: str, data_root: Path) -> dict[str, JsonValue]:
    """Load a source record only if both the record and the stored bytes are still intact."""
    manifest = _load_source_record(source_sha256, data_root)
    source = manifest["source"]
    if not isinstance(source, dict):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "source record has no source section")
    stored = source_directory(data_root, source_sha256) / str(source["stored_name"])
    if not stored.is_file() or sha256_file(stored) != source_sha256:
        raise CorpusRefusal(
            RefusalCode.SOURCE_HASH_MISMATCH,
            "stored source bytes do not match the imported hash",
            {"source_sha256": source_sha256},
        )
    return manifest


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
    manifest = load_verified_source(stream.source_sha256, data_root)
    require_policy(
        manifest["decode_policy_sha256"], policy_sha256, f"source {stream.source_sha256}"
    )
    media = manifest["sequence"]
    if not isinstance(media, dict) or not isinstance(media["frame_count"], int):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "source record has no sequence section")
    return {
        "stream_id": stream.stream_id,
        "modality": CAMERA_MODALITY,
        "encounter_id": encounter.encounter_id,
        "group_id": group.group_id,
        "split": group.split,
        "source_sha256": stream.source_sha256,
        "source_manifest_sha256": manifest[SEAL_FIELD],
        "selection": _resolve_selection(stream, media["frame_count"]),
        "frame_count": media["frame_count"],
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
    existing = read_sealed(target, CORPUS_MANIFEST_KIND)
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
