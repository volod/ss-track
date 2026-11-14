"""A staged pool version across three splits, a discovery run over it, and review files."""

from pathlib import Path
from typing import Any

import yaml

from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.discovery.run import run_discovery
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.review.export import export_review
from tests.corpus.conftest import encounter_of, group_of, stream_of, write_groups

POOL = "pilot-v1"
RUN_ID = "discovery-1"
FROZEN = "frozen-v1"
LINKS = "links-1"
PLAN = {
    "schema_version": 1,
    "run_id": RUN_ID,
    "corpus_id": POOL,
    "source_approval": {"owner": "project owner", "reference": "fixture-media"},
    "pool": {"window_frames": 8},
    "audit": {"seed": 7, "sample_size": 3},  # every window of every group: all are offered
    "selection": {"method": "uniform", "budget": 2, "seed": 3},
}


def pool_groups(
    first: ImportResult, second: ImportResult, third: ImportResult
) -> list[dict[str, object]]:
    """Stream one in development, two in calibration and three in the locked split."""
    return [
        group_of("site-a", "development", encounter_of("enc-one", stream_of(first))),
        group_of(
            "site-b", "calibration", encounter_of("enc-two", stream_of(second, stream_id="two"))
        ),
        group_of("held", "locked", encounter_of("enc-three", stream_of(third, stream_id="three"))),
    ]


def stage_pool(
    media: Path, data_root: Path, first: ImportResult, second: ImportResult, third: ImportResult
) -> None:
    """Build and stage the pool version, then write the discovery run over it."""
    build_corpus(write_groups(media, pool_groups(first, second, third)), data_root)
    stage_corpus(POOL, data_root)
    plan = media / "plan.yaml"
    plan.write_text(yaml.safe_dump(PLAN), encoding="ascii")
    run_discovery(plan, data_root)


def include(stream_id: str, candidate_id: str, observation: str = "target_present") -> Any:
    return {
        "stream_id": stream_id,
        "candidate_id": candidate_id,
        "decision": "include",
        "observation": observation,
    }


def exclude(stream_id: str, candidate_id: str, reason: str, **fields: object) -> Any:
    return {
        "stream_id": stream_id,
        "candidate_id": candidate_id,
        "decision": "exclude",
        "observation": "unknown",
        "reason": reason,
    } | fields


def write_review(path: Path, *decisions: Any, run_id: str = RUN_ID) -> Path:
    document = {"schema_version": 1, "run_id": run_id, "reviewer": "site lead"}
    path.write_text(yaml.safe_dump(document | {"decisions": list(decisions)}), encoding="ascii")
    return path


# Windows one/pool-000 and pool-001 join into one stream; two/pool-002 is its own; one/pool-002
# is excluded and two/pool-000 and pool-001 are left unreviewed.
STOCK_DECISIONS = (
    include("one", "pool-000"),
    include("one", "pool-001", "unknown"),
    exclude("one", "pool-002", "quality", note="blurred"),
    include("two", "pool-002", "confuser"),
)


def export_stock(
    media: Path, data_root: Path, *, corpus_id: str = FROZEN, **options: Any
) -> tuple[Path, Any]:
    """Export the stock review and return the declaration path and the result."""
    review = write_review(media / "review.yaml", *STOCK_DECISIONS)
    out = media / f"{corpus_id}.yaml"
    return out, export_review(review, corpus_id, out, data_root, **options)


def staged(media: Path, data_root: Path, **options: Any) -> Path:
    """Export the stock review, build and stage its version, review its links; return the review."""
    out, _ = export_stock(media, data_root, **options)
    build_corpus(out, data_root)
    stage_corpus(options.get("corpus_id", FROZEN), data_root)
    return media / "review.yaml"


def review_links(
    data_root: Path, corpus_id: str = FROZEN, run_id: str = LINKS, **fields: Any
) -> str:
    write_links(LinkRequest(run_id, corpus_id, **fields), data_root)
    return run_id
