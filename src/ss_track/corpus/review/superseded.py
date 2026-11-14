"""Apply a link review's related decisions to the versions a frozen one supersedes.

A link review covers one version, so a recording related to one that a superseded version held in
another split is not a link there: its decision is listed outside the links, as naming a source the
version does not hold. Material a version held has been seen, so a frozen version must not put a
recording in one split while an older version of its chain held a related recording in another.
Each such pair is `SPLIT_LEAKAGE`, named with both places and the reviewer's decision.
"""

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.links.decisions import RELATED
from ss_track.corpus.records.projections import OTHER_SCHEMA, Unprojected
from ss_track.corpus.versions.manifests import load_predecessor
from ss_track.corpus.versions.predecessors import Predecessor, follow_links

type Place = dict[str, JsonValue]


def related_pairs(links: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return every related decision a link review holds, inside its links or outside them."""
    inside = [
        {"sources": [source["source_sha256"] for source in link["sources"]], **link["decision"]}
        for link in links["links"]
        if link.get("decision", {}).get("decision") == RELATED
    ]
    outside = [
        item for item in links.get("decisions_outside_links", []) if item["decision"] == RELATED
    ]
    return [*inside, *outside]


def _places(version: Mapping[str, Any]) -> dict[str, Place]:
    return {
        str(stream["source_sha256"]): {
            "corpus_id": version["corpus_id"],
            "group_id": stream["group_id"],
            "split": stream["split"],
        }
        for stream in version["streams"]
    }


def _apart(
    decision: Mapping[str, Any], frozen: Mapping[str, Place], older: Mapping[str, Place]
) -> Iterator[JsonValue]:
    """Yield each orientation of a related pair the frozen version and an older one split apart."""
    first, second = (str(source) for source in decision["sources"])
    for here, there in ((first, second), (second, first)):
        if here in frozen and there in older and frozen[here]["split"] != older[there]["split"]:
            entry: dict[str, JsonValue] = {
                "source_sha256": here,
                "place": frozen[here],
                "related_source_sha256": there,
                "related_place": older[there],
                "decision": RELATED,
            }
            if "note" in decision:
                entry["note"] = decision["note"]
            yield entry


def require_related_together(
    corpus: Mapping[str, Any], links: Mapping[str, Any], data_root: Path
) -> dict[str, JsonValue]:
    """Refuse a related recording an older version of the chain held in another split.

    Returns what was compared: the projected versions, nearest first, and those whose major keeps
    no placement.
    """
    chain: Sequence[Predecessor] = list(
        follow_links(corpus, lambda corpus_id: load_predecessor(corpus_id, data_root))
    )
    frozen = _places(corpus)
    decisions = related_pairs(links)
    apart: list[JsonValue] = [
        entry
        for version in chain
        if not isinstance(version, Unprojected)
        for decision in decisions
        for entry in _apart(decision, frozen, _places(version))
    ]
    if apart:
        raise CorpusRefusal(
            RefusalCode.SPLIT_LEAKAGE,
            f"{len(apart)} recording(s) sit in another split than a related recording a "
            "superseded version held; keep related recordings in one split across the chain",
            {"corpus_id": corpus["corpus_id"], "related_apart": apart},
        )
    return {
        "compared_versions": [
            version["corpus_id"] for version in chain if not isinstance(version, Unprojected)
        ],
        "not_compared": [
            {"corpus_id": version.corpus_id, "reason": OTHER_SCHEMA}
            for version in chain
            if isinstance(version, Unprojected)
        ],
    }
