"""`ss-track discover run` and `discover verify`: write one discovery run from a plan, or verify one.

A run reads a staged corpus version. Each pinned extractor embeds every bundle's frames in its own
worker process; each hint file's matches become sibling windows through the hash join and the slot
rule; every bundle is tiled into pool windows, and the audit sample is drawn from them per
encounter group. A plan with a selection then scores every candidate and ranks pool windows by its
method. Nothing is written until every extractor and hint file has answered, and a run id is held
by one command at a time, so a refused or interrupted run leaves no partial run behind. Verifying a
run also recomputes its scores and selection from its feature rows and the staged frames.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.metadata import project_info
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import exclusive_lock
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.frame_set import read_frame_set
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.discovery.features import FeatureFile, seal_feature_rows
from ss_track.corpus.discovery.plan import DiscoveryPlan, read_discovery_plan
from ss_track.corpus.discovery.pool import audit_design, draw_audit, stream_candidates, stream_pool
from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.discovery.records import DiscoveryRecords, seal_discovery, write_discovery
from ss_track.corpus.discovery.result import DiscoveryResult
from ss_track.corpus.discovery.selection_check import require_reproduced
from ss_track.corpus.discovery.sibling_check import stream_timing
from ss_track.corpus.selection.apply import (
    Selection,
    locked_streams,
    planned,
    score_and_select,
    unranked,
)
from ss_track.corpus.selection.catalog import score_specs
from ss_track.corpus.siblings.embedding import embed_streams, require_extractors
from ss_track.corpus.siblings.video_hints import (
    HintMapping,
    HintSource,
    map_hints,
    read_hint_source,
)
from ss_track.corpus.siblings.worker_env import worker_python
from ss_track.corpus.siblings.worker_process import DEFAULT_TIMEOUT_SEC
from ss_track.corpus.storage.layout import discovery_root, discovery_run_path, frames_root
from ss_track.corpus.versions.manifests import load_corpus_manifest

WRITTEN = "written"
UNCHANGED = "unchanged"
VERIFIED = "verified"
PROCESSING_REVISION = 1


def _streams(corpus: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sorted(corpus["streams"], key=lambda stream: str(stream["stream_id"]))


def _lines(frame_set: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {line["stream_id"]: line for line in frame_set["bundles"]}


def _inventory_body(
    plan: DiscoveryPlan,
    stream: Mapping[str, Any],
    line: Mapping[str, Any],
    candidates: list[JsonValue],
) -> dict[str, JsonValue]:
    return {
        "run_id": plan.run_id,
        "corpus_id": plan.corpus_id,
        "stream_id": stream["stream_id"],
        "group_id": stream["group_id"],
        "bundle_sha256": line["bundle_sha256"],
        "source_sha256": line["source_sha256"],
        "source_manifest_sha256": line["source_manifest_sha256"],
        "bundle_frames": dict(stream["selection"]),
        "candidates": candidates,
    }


def _map_hints(
    sources: Sequence[HintSource], inventories: Sequence[Mapping[str, Any]], data_root: Path
) -> dict[str, HintMapping]:
    if not sources:
        return {}
    timings = [stream_timing(inventory, data_root) for inventory in inventories]
    return {source.hint_source_id: map_hints(source, timings) for source in sources}


def _features(
    plan: DiscoveryPlan,
    bundles: Sequence[FrameBundle],
    environ: Mapping[str, str] | None,
    timeout: float,
) -> tuple[list[JsonValue], list[FeatureFile]]:
    embedding = plan.embedding
    if embedding is None:
        return [], []
    python = worker_python(environ)
    if len(embedding.extractors) > 1:
        require_extractors(embedding, python=python, timeout=timeout, environ=environ)
    extractors: list[dict[str, JsonValue]] = []
    files: list[FeatureFile] = []
    for extractor in embedding.extractors:
        for rows in embed_streams(
            embedding, extractor, bundles, python=python, timeout=timeout, environ=environ
        ):
            extractors.append(rows.provenance)
            files += [
                seal_feature_rows(
                    plan.run_id,
                    plan.corpus_id,
                    str(rows.provenance["extractor_id"]),
                    stream,
                    embedding.frame_stride,
                    extractor.dimensions,
                )
                for stream in rows.streams
            ]
    extractors.sort(key=lambda provenance: str(provenance["extractor_id"]))
    return list(extractors), files


def _selection(plan: DiscoveryPlan) -> Selection:
    if plan.selection is None:
        return unranked()
    scores = score_specs(
        [
            (extractor.extractor_id, [view_id for view_id, _ in extractor.views()])
            for extractor in plan.extractors()
        ]
    )
    chosen = plan.selection
    return planned(chosen.method, chosen.budget, chosen.seed, chosen.score_ids, scores)


def build_discovery(
    plan: DiscoveryPlan,
    data_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> DiscoveryRecords:
    """Compute and seal every record of one run, writing nothing."""
    sources = [read_hint_source(hint.path, hint.hint_source_id) for hint in plan.hints]
    corpus = load_corpus_manifest(plan.corpus_id, data_root)
    frame_set = read_frame_set(data_root, plan.corpus_id)
    lines = _lines(frame_set)
    streams = _streams(corpus)
    root = frames_root(data_root, plan.corpus_id)
    bundles = [open_corpus_bundle(str(stream["stream_id"]), corpus, root) for stream in streams]
    pools = {
        str(stream["stream_id"]): stream_pool(
            str(stream["stream_id"]),
            str(stream["group_id"]),
            stream["selection"],
            plan.window_frames,
        )
        for stream in streams
    }
    draw = draw_audit(
        (window for pool in pools.values() for window in pool),
        plan.audit_seed,
        plan.audit_sample_size,
    )
    shells = [_inventory_body(plan, stream, lines[stream["stream_id"]], []) for stream in streams]
    mappings = _map_hints(sources, shells, data_root)
    hint_windows = {name: mapping.windows for name, mapping in mappings.items()}
    inventories = [
        {
            **shell,
            "candidates": stream_candidates(
                pools[str(shell["stream_id"])], draw, hint_windows, str(shell["stream_id"])
            ),
        }
        for shell in shells
    ]
    extractors, features = _features(plan, bundles, environ, timeout)
    selection = _selection(plan)
    inventories = score_and_select(
        selection,
        inventories,
        {feature.name: feature for feature in features},
        bundles,
        locked_streams(corpus),
    )
    run_body: dict[str, JsonValue] = {
        "run_id": plan.run_id,
        "corpus_id": plan.corpus_id,
        "frame_set_sha256": frame_set[SEAL_FIELD],
        "processing": {"ss_track_version": project_info().version, "revision": PROCESSING_REVISION},
        "extractors": extractors,
        "scores": selection.run_scores(),
        "hint_sources": [source.to_run(mappings[source.hint_source_id]) for source in sources],
        "pool": {"window_frames": plan.window_frames},
        "selection": selection.run_selection(),
        "audit": audit_design(draw, plan.audit_seed),
        "source_approval": {"owner": plan.approval_owner, "reference": plan.approval_reference},
    }
    return seal_discovery(run_body, inventories, features)


def run_discovery(
    plan_path: Path,
    data_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> DiscoveryResult:
    """Write the run a plan declares, holding its run id so no other command computes it too."""
    plan = read_discovery_plan(plan_path)
    busy = CorpusRefusal(
        RefusalCode.DISCOVERY_IN_PROGRESS,
        "another command is writing this discovery run",
        {"run_id": plan.run_id},
    )
    with exclusive_lock(discovery_root(data_root), f".run-{plan.run_id}.lock", busy=busy):
        records = build_discovery(plan, data_root, environ=environ, timeout=timeout)
        written = write_discovery(data_root, records)
    status = WRITTEN if written.written else UNCHANGED
    return DiscoveryResult(status, records, written.path, _frame_sizes(records, data_root))


def _frame_sizes(records: DiscoveryRecords, data_root: Path) -> dict[str, tuple[int, int]]:
    corpus_id = str(records.run["corpus_id"])
    corpus = load_corpus_manifest(corpus_id, data_root)
    root = frames_root(data_root, corpus_id)
    bundles = (open_corpus_bundle(stream_id, corpus, root) for stream_id in records.inventories)
    return {bundle.stream_id: (bundle.width, bundle.height) for bundle in bundles}


def verify_discovery_run(run_id: str, data_root: Path) -> DiscoveryResult:
    """Verify a written run against the corpus version it read, recomputing its selection."""
    records = verify_discovery(data_root, run_id)
    require_reproduced(records, data_root)
    path = discovery_run_path(data_root, run_id)
    return DiscoveryResult(VERIFIED, records, path, _frame_sizes(records, data_root))
