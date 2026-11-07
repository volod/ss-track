"""The rules of a discovery run record, alone and against the inventories it seals.

A run states its extractors, scores, hint sources and audit strata once, and every inventory names
them by id. These checks keep each id unique and ordered, each reference declared, and each total
the run states equal to what its inventories hold.
"""

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.corpus.discovery.findings import RUN_RECORD, Finding

SELECTED = "selected"
POOL = "pool"
SAMPLED = "sampled"
NOT_SAMPLED = "not_sampled"
_AUDITED = (SAMPLED, NOT_SAMPLED)

# Each list of the run, by its pointer and the key that identifies its entries.
_ID_LISTS = (
    ("/extractors", "extractor_id"),
    ("/scores", "score_id"),
    ("/hint_sources", "hint_source_id"),
    ("/audit/strata", "stratum_id"),
    ("/inventories", "stream_id"),
)
_EXTRACTOR_LISTS = (("libraries", "name"), ("weights", "name"))


def _at(record: Mapping[str, Any], pointer: str) -> list[Any]:
    node: Any = record
    for part in pointer.strip("/").split("/"):
        node = node[part]
    return list(node)


def ordered(values: Sequence[Any], record: str, pointer: str, what: str) -> Iterator[Finding]:
    """Find a list that is not strictly ascending, which is how each id is also unique."""
    for index in range(1, len(values)):
        if not values[index - 1] < values[index]:
            yield Finding(
                record,
                f"{pointer}/{index}",
                "order",
                f"{what} {values[index]!r} is not after {values[index - 1]!r}",
            )


def ids(entries: Sequence[Mapping[str, Any]], key: str) -> list[Any]:
    """Return the identifying values of a list's entries, in list order."""
    return [entry[key] for entry in entries]


def run_findings(run: Mapping[str, Any]) -> list[Finding]:
    """Check what a run states about itself."""
    return [*_order(run), *_references(run), *_strata(run)]


def _order(run: Mapping[str, Any]) -> Iterator[Finding]:
    for pointer, key in _ID_LISTS:
        yield from ordered(ids(_at(run, pointer), key), RUN_RECORD, pointer, key)
    for index, extractor in enumerate(run["extractors"]):
        for name, key in _EXTRACTOR_LISTS:
            pointer = f"/extractors/{index}/{name}"
            yield from ordered(ids(extractor[name], key), RUN_RECORD, pointer, key)
    for index, score in enumerate(run["scores"]):
        pointer = f"/scores/{index}/extractor_ids"
        yield from ordered(score["extractor_ids"], RUN_RECORD, pointer, "extractor_id")
    selection = run["selection"]["score_ids"]
    yield from ordered(selection, RUN_RECORD, "/selection/score_ids", "score_id")


def _references(run: Mapping[str, Any]) -> Iterator[Finding]:
    extractors = set(ids(run["extractors"], "extractor_id"))
    for index, score in enumerate(run["scores"]):
        for position, extractor_id in enumerate(score["extractor_ids"]):
            if extractor_id not in extractors:
                pointer = f"/scores/{index}/extractor_ids/{position}"
                message = f"score names undeclared extractor {extractor_id!r}"
                yield Finding(RUN_RECORD, pointer, "references", message)
    scores = set(ids(run["scores"], "score_id"))
    for position, score_id in enumerate(run["selection"]["score_ids"]):
        if score_id not in scores:
            pointer = f"/selection/score_ids/{position}"
            message = f"selection reads undeclared score {score_id!r}"
            yield Finding(RUN_RECORD, pointer, "references", message)


def _strata(run: Mapping[str, Any]) -> Iterator[Finding]:
    for index, stratum in enumerate(run["audit"]["strata"]):
        if stratum["sample_size"] > stratum["eligible_count"]:
            pointer = f"/audit/strata/{index}/sample_size"
            message = "a stratum cannot draw more windows than it holds"
            yield Finding(RUN_RECORD, pointer, "audit", message)


def totals_findings(
    run: Mapping[str, Any], inventories: Mapping[str, Mapping[str, Any]]
) -> list[Finding]:
    """Check the run's lines, ranks and strata against the inventories they seal."""
    return [*_lines(run, inventories), *_ranks(run, inventories), *_counts(run, inventories)]


def _lines(
    run: Mapping[str, Any], inventories: Mapping[str, Mapping[str, Any]]
) -> Iterator[Finding]:
    for index, line in enumerate(run["inventories"]):
        inventory = inventories.get(line["stream_id"])
        pointer = f"/inventories/{index}"
        if inventory is None:
            yield Finding(RUN_RECORD, pointer, "inventories", "the stream has no inventory")
            continue
        expected = {
            "inventory_sha256": inventory[SEAL_FIELD],
            "bundle_sha256": inventory["bundle_sha256"],
            "source_manifest_sha256": inventory["source_manifest_sha256"],
            "candidate_count": len(inventory["candidates"]),
        }
        for key, value in expected.items():
            if line[key] != value:
                message = f"{key} differs from the stream's inventory"
                yield Finding(RUN_RECORD, f"{pointer}/{key}", "inventories", message)
    for stream_id in sorted(set(inventories) - set(ids(run["inventories"], "stream_id"))):
        message = f"inventory of {stream_id!r} has no line in the run"
        yield Finding(RUN_RECORD, "/inventories", "inventories", message)


def _candidates(inventories: Mapping[str, Mapping[str, Any]]) -> Iterator[Mapping[str, Any]]:
    for stream_id in sorted(inventories):
        yield from inventories[stream_id]["candidates"]


def _ranks(
    run: Mapping[str, Any], inventories: Mapping[str, Mapping[str, Any]]
) -> Iterator[Finding]:
    ranks = sorted(
        candidate["selection"]["rank"]
        for candidate in _candidates(inventories)
        if candidate["selection"]["status"] == SELECTED
    )
    if ranks != list(range(1, len(ranks) + 1)):
        message = "selected candidates must hold ranks 1 to their count, each once"
        yield Finding(RUN_RECORD, "/selection", "selection", message)
    if len(ranks) > run["selection"]["budget"]:
        message = f"{len(ranks)} candidates selected over a budget of {run['selection']['budget']}"
        yield Finding(RUN_RECORD, "/selection/budget", "selection", message)


def _counts(
    run: Mapping[str, Any], inventories: Mapping[str, Mapping[str, Any]]
) -> Iterator[Finding]:
    eligible: Counter[str] = Counter()
    sampled: Counter[str] = Counter()
    for candidate in _candidates(inventories):
        audit = candidate["audit"]
        if audit["status"] in _AUDITED:
            eligible[audit["stratum_id"]] += 1
            sampled[audit["stratum_id"]] += audit["status"] == SAMPLED
    for index, stratum in enumerate(run["audit"]["strata"]):
        name = stratum["stratum_id"]
        for key, found in (("eligible_count", eligible[name]), ("sample_size", sampled[name])):
            if stratum[key] != found:
                message = f"stratum states {stratum[key]} but the inventories hold {found}"
                yield Finding(RUN_RECORD, f"/audit/strata/{index}/{key}", "audit", message)
