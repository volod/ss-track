"""Bind a discovery run to the staged corpus version it read: its frame set and its manifest.

The frame set names each stream's bundle and the source record whose terms it rests on, so a run
that agrees with it rests on those records; the corpus manifest names each stream's group and the
frames its bundle holds. A generated case is fixture material, not discovered video, so no
inventory may cover one. Each sibling window must be what the slot rule maps its slot to, and each
feature record must name exactly the frames of its bundle at its stride, by their sealed hashes.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.frame_set import read_frame_set
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.discovery.features import FeatureFile
from ss_track.corpus.discovery.features import binding_findings as rows_findings
from ss_track.corpus.discovery.findings import (
    RUN_RECORD,
    Finding,
    inventory_label,
    require_no_findings,
)
from ss_track.corpus.discovery.sibling_check import sibling_findings
from ss_track.corpus.records.read_refusals import incomplete_record
from ss_track.corpus.storage.layout import DISCOVERY_RUN_NAME, frames_root
from ss_track.corpus.versions.manifests import load_corpus_manifest

_FRAME_SET_FIELDS = ("bundle_sha256", "source_sha256", "source_manifest_sha256")


def require_bound(
    data_root: Path,
    run: Mapping[str, Any],
    inventories: Mapping[str, Mapping[str, Any]],
    features: Mapping[str, FeatureFile] | None = None,
) -> None:
    """Refuse a run unless it names exactly what its corpus version staged on this data root."""
    corpus_id = str(run["corpus_id"])
    corpus = load_corpus_manifest(corpus_id, data_root)
    frame_set = read_frame_set(data_root, corpus_id)
    if run["frame_set_sha256"] != frame_set[SEAL_FIELD]:
        raise CorpusRefusal(
            RefusalCode.FRAME_SET_MISMATCH,
            "the run read another frame set than this corpus version holds",
            {
                "run_id": run["run_id"],
                "corpus_id": corpus_id,
                "pinned_frame_set_sha256": run["frame_set_sha256"],
                "found_frame_set_sha256": frame_set[SEAL_FIELD],
            },
        )
    with incomplete_record(DISCOVERY_RUN_NAME):
        found = binding_findings(run, inventories, frame_set, corpus)
        if not found:
            found += sibling_findings(run, inventories, data_root)
            found += _feature_findings(features or {}, corpus, data_root)
    require_no_findings(found, str(run["run_id"]))


def _feature_findings(
    features: Mapping[str, FeatureFile], corpus: Mapping[str, Any], data_root: Path
) -> list[Finding]:
    root = frames_root(data_root, str(corpus["corpus_id"]))
    bundles: dict[str, FrameBundle] = {}
    found: list[Finding] = []
    for name, feature in sorted(features.items()):
        stream_id = feature.stream_id
        if stream_id not in bundles:
            bundles[stream_id] = open_corpus_bundle(stream_id, corpus, root)
        found += rows_findings(feature.record, bundles[stream_id], name)
    return found


def binding_findings(
    run: Mapping[str, Any],
    inventories: Mapping[str, Mapping[str, Any]],
    frame_set: Mapping[str, Any],
    corpus: Mapping[str, Any],
) -> list[Finding]:
    """Check that a run and its inventories name exactly what this corpus version staged."""
    found = [*_corpus(frame_set, corpus)]
    lines = {line["stream_id"]: line for line in frame_set["bundles"]}
    streams = {stream["stream_id"]: stream for stream in corpus["streams"]}
    for stream_id, inventory in sorted(inventories.items()):
        found += _inventory(inventory, lines.get(stream_id), streams.get(stream_id))
    return found


def _corpus(frame_set: Mapping[str, Any], corpus: Mapping[str, Any]) -> Iterator[Finding]:
    if frame_set["corpus_manifest_sha256"] != corpus[SEAL_FIELD]:
        message = "the frame set binds another corpus manifest than this version holds"
        yield Finding(RUN_RECORD, "/corpus_id", "inventories", message)


def _inventory(
    inventory: Mapping[str, Any],
    line: Mapping[str, Any] | None,
    stream: Mapping[str, Any] | None,
) -> Iterator[Finding]:
    label = inventory_label(inventory["stream_id"])
    if line is None or stream is None or line["parent_stream_id"] is not None:
        message = "the inventory must cover a stream of the corpus version, not a generated case"
        yield Finding(label, "/stream_id", "binding", message)
        return
    for key in _FRAME_SET_FIELDS:
        if inventory[key] != line[key]:
            yield Finding(label, f"/{key}", "binding", f"{key} differs from the frame set")
    if inventory["group_id"] != stream["group_id"]:
        yield Finding(label, "/group_id", "binding", "group_id differs from the corpus manifest")
    if inventory["bundle_frames"] != stream["selection"]:
        message = "bundle_frames differs from the frames the corpus manifest selects"
        yield Finding(label, "/bundle_frames", "binding", message)
