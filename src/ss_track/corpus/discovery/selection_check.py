"""Recompute a written run's scores and selection, and refuse one that is not what its methods give.

A run states every score's method, revision and extractors and its selection's method, budget, seed
and scores read, so its feature rows and the staged frames determine every value and decision. A
recorded score or selection that differs, a method this ss-track does not know, and a locked stream
that selection ranked are all `RECORD_INVALID`. Score values are compared as written, so the check
holds on the host that wrote the run, and elsewhere unless the backbone rows' last digits differ.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.discovery.findings import (
    RUN_RECORD,
    Finding,
    inventory_label,
    require_no_findings,
)
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.selection.apply import from_run, locked_streams, score_and_select
from ss_track.corpus.storage.layout import frames_root
from ss_track.corpus.versions.manifests import load_corpus_manifest

_CHECKED = ("scores", "selection")


def require_reproduced(records: DiscoveryRecords, data_root: Path) -> None:
    """Refuse a run whose scores or selection its own feature rows and frames do not give."""
    run: Mapping[str, Any] = records.run
    selection = from_run(run)
    corpus = load_corpus_manifest(str(run["corpus_id"]), data_root)
    root = frames_root(data_root, str(run["corpus_id"]))
    inventories = [records.inventories[name] for name in sorted(records.inventories)]
    bundles = (open_corpus_bundle(str(item["stream_id"]), corpus, root) for item in inventories)
    recomputed = score_and_select(
        selection, inventories, records.features, bundles, locked_streams(corpus)
    )
    found = [
        Finding(RUN_RECORD, f"/{key}", "selection", f"the run's methods state {key} {value!r}")
        for key, value in (
            ("scores", selection.run_scores()),
            ("selection", selection.run_selection()),
        )
        if run[key] != value
    ]
    found += [
        finding
        for written, expected in zip(inventories, recomputed, strict=True)
        for finding in _differences(written, expected)
    ]
    require_no_findings(found, str(run["run_id"]))


def _differences(written: Mapping[str, Any], expected: Mapping[str, Any]) -> Iterator[Finding]:
    label = inventory_label(str(written["stream_id"]))
    pairs = zip(written["candidates"], expected["candidates"], strict=True)
    for index, (found, computed) in enumerate(pairs):
        for key in _CHECKED:
            if found[key] != computed[key]:
                yield Finding(
                    label,
                    f"/candidates/{index}/{key}",
                    "selection",
                    f"the run's methods give {key} {computed[key]!r}",
                )
