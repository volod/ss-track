"""Read a link review back as evidence: its seal, its contract and every rule the contract states.

A seal proves only that a record matches itself, so the contract is checked too, and then the rules
the dialect cannot state: a link joins two groups, its status follows its decision, the review's
status follows its links, and its lists keep their order. A record that breaks one is
`RECORD_INVALID`, so a later step that trusts a `clear` review cannot be handed a forged one.
"""

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.links.review import CLEAR, UNRESOLVED
from ss_track.corpus.records.kinds import CORPUS_LINKS
from ss_track.corpus.storage.layout import LINKS_NAME, links_path
from ss_track.schema.validation.enforce import is_shared_type, require_record


def _sources(link: Mapping[str, Any]) -> list[str]:
    return [str(source["source_sha256"]) for source in link["sources"]]


def _link_findings(position: int, link: Mapping[str, Any]) -> Iterator[str]:
    first, second = link["sources"]
    if first["group_id"] == second["group_id"]:
        yield f"links[{position}] joins one group to itself"
    if not first["source_sha256"] < second["source_sha256"]:
        yield f"links[{position}] names its sources out of order"
    if link["cross_split"] != (first["split"] != second["split"]):
        yield f"links[{position}] states cross_split against its splits"
    decision = link.get("decision")
    expected = UNRESOLVED if decision is None else decision["decision"]
    if link["status"] != expected:
        yield f"links[{position}] has status {link['status']} against its decision"


def _findings(record: Mapping[str, Any]) -> Iterator[str]:
    links: Sequence[Mapping[str, Any]] = record["links"]
    for position, link in enumerate(links):
        yield from _link_findings(position, link)
    pairs = [_sources(link) for link in links]
    if pairs != sorted(pairs) or len({tuple(pair) for pair in pairs}) != len(pairs):
        yield "links are not in ascending source order, each pair once"
    expected = UNRESOLVED if any(link["status"] == UNRESOLVED for link in links) else CLEAR
    if record["status"] != expected:
        yield f"status is {record['status']} against its links"
    if ("review" in record) != ("decisions_outside_links" in record):
        yield "review and decisions_outside_links appear together"


def read_links(data_root: Path, run_id: str) -> dict[str, JsonValue]:
    """Read one link review, refusing a missing, altered or rule-breaking record."""
    path = links_path(data_root, run_id)
    if not is_shared_type("identifier", run_id) or not path.is_file():
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "no such link review",
            {"record": LINKS_NAME, "run_id": run_id},
        )
    record = read_sealed(path, CORPUS_LINKS)
    require_record(record)
    findings = list(_findings(record))
    if findings:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID,
            "a link review breaks a rule its contract states",
            {"record": LINKS_NAME, "run_id": run_id, "findings": list(findings)},
        )
    return record
