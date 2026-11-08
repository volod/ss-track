"""`ss-track corpus freeze`: seal a built and staged corpus version as the one a review makes.

Freezing trusts nothing the export wrote. It checks the version's current source terms, replays
the review against the verified discovery run and requires the version to hold exactly the streams
that replay makes, reads the version's link review with `read_links` bound to this manifest and
frame set, refuses an undecided link across splits, applies the reviewer's related decisions to
every version this one supersedes, and verifies every frame. Only then is the freeze record sealed
beside the manifest. The same inputs write the same bytes, so a retry reports `unchanged`.
"""

from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.verification import verify_corpus_frames
from ss_track.corpus.bundles.version_bundles import require_sources_hold
from ss_track.corpus.links.records import read_links
from ss_track.corpus.links.review import UNRESOLVED
from ss_track.corpus.links.run import staged_frame_set
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.review.export import Reviewed, apply_review, require_current_terms
from ss_track.corpus.review.freeze_record import freeze_body, read_freeze
from ss_track.corpus.review.result import FreezeResult, review_counts
from ss_track.corpus.review.superseded import require_related_together
from ss_track.corpus.sources.terms import evaluation_date
from ss_track.corpus.storage.layout import FREEZE_LOCK, corpus_root, freeze_path
from ss_track.corpus.storage.scratch import exclusive_lock
from ss_track.corpus.versions.manifests import load_corpus_manifest

FROZEN = "frozen"
UNCHANGED = "unchanged"
_PLACEMENT = ("stream_id", "encounter_id", "group_id", "split", "source_sha256", "selection")


def require_replayed(corpus: Mapping[str, Any], reviewed: Reviewed) -> None:
    """Refuse a version that does not hold exactly the streams the review makes of its run."""
    expected = {member.stream_id: member.placement() for member in reviewed.membership.members}
    found = {
        str(stream["stream_id"]): {key: stream[key] for key in _PLACEMENT}
        for stream in corpus["streams"]
    }
    pool = reviewed.pool
    differences: dict[str, JsonValue] = {
        "missing": list[JsonValue](sorted(expected.keys() - found.keys())),
        "unexpected": list[JsonValue](sorted(found.keys() - expected.keys())),
        "changed": list[JsonValue](
            sorted(key for key in expected.keys() & found.keys() if expected[key] != found[key])
        ),
        "fields": [
            name
            for name, same in (
                (
                    "decode_policy_sha256",
                    corpus["decode_policy_sha256"] == pool["decode_policy_sha256"],
                ),
                ("scenario_rights", corpus["scenario_rights"] == pool["scenario_rights"]),
                ("generated_cases", corpus["generated_cases"] == []),
            )
            if not same
        ],
    }
    if any(differences.values()):
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this corpus version is not the one the review makes of its run; export the review "
            "and build that declaration as a new version",
            {"corpus_id": corpus["corpus_id"], "run_id": reviewed.queue.run_id, **differences},
        )


def require_links_hold(
    corpus: Mapping[str, Any], frame_set: Mapping[str, Any], links: Mapping[str, Any]
) -> None:
    """Refuse a link review of other frames, or one that leaves a link across splits undecided."""
    pins = {
        "corpus_manifest_sha256": corpus[SEAL_FIELD],
        "frame_set_sha256": frame_set[SEAL_FIELD],
    }
    if any(links[key] != value for key, value in pins.items()):
        raise CorpusRefusal(
            RefusalCode.FRAME_SET_MISMATCH,
            "the link review read another corpus version or frame set than this one",
            {
                "corpus_id": corpus["corpus_id"],
                "links_run_id": links["run_id"],
                **{f"found_{key}": value for key, value in pins.items()},
                **{f"pinned_{key}": links[key] for key in pins},
            },
        )
    open_links = [
        link for link in links["links"] if link["status"] == UNRESOLVED and link["cross_split"]
    ]
    if open_links:
        raise CorpusRefusal(
            RefusalCode.LINKS_UNRESOLVED,
            f"{len(open_links)} link(s) across splits are undecided; decide each pair related or "
            "unrelated and review the links again",
            {
                "corpus_id": corpus["corpus_id"],
                "links_run_id": links["run_id"],
                "links": open_links,
            },
        )


def _publish(data_root: Path, corpus: Mapping[str, Any], record: dict[str, JsonValue]) -> bool:
    """Write the record once; the same record again changes nothing, another is refused."""
    path = freeze_path(data_root, str(corpus["corpus_id"]))
    with exclusive_lock(corpus_root(data_root), FREEZE_LOCK):
        if not path.exists():
            write_sealed(path, record)
            return True
        existing = read_freeze(data_root, corpus)
    if existing[SEAL_FIELD] != record[SEAL_FIELD]:
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this corpus version is already frozen from other decisions; freeze a new version",
            {
                "corpus_id": corpus["corpus_id"],
                "manifest_sha256": existing[SEAL_FIELD],
                "proposed_manifest_sha256": record[SEAL_FIELD],
            },
        )
    return False


def freeze_corpus(
    corpus_id: str,
    review_path: Path,
    links_run_id: str,
    data_root: Path,
    *,
    today: date | None = None,
) -> FreezeResult:
    """Freeze one built and staged corpus version as the one its review makes."""
    checked_on = evaluation_date(today)
    corpus = load_corpus_manifest(corpus_id, data_root)
    require_sources_hold(corpus, data_root, checked_on)
    reviewed = apply_review(review_path, data_root)
    require_current_terms(reviewed, data_root, checked_on)
    require_replayed(corpus, reviewed)
    frame_set = staged_frame_set(corpus_id, data_root)
    links = read_links(data_root, links_run_id)
    require_links_hold(corpus, frame_set, links)
    superseded = require_related_together(corpus, links, data_root)
    frames = verify_corpus_frames(corpus_id, data_root, today=checked_on)
    record = seal(freeze_body(corpus, frames.frame_set_sha256, reviewed, links, superseded))
    written = _publish(data_root, corpus, record)
    return FreezeResult(
        FROZEN if written else UNCHANGED,
        record,
        freeze_path(data_root, corpus_id),
        review_counts(reviewed.queue, reviewed.membership),
    )
