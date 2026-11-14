"""Durable checkpoints for interactive review in the existing link-decisions format."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.links.decisions import Decision, SourcePair, read_decisions, source_pair
from ss_track.corpus.storage.scratch import write_atomically

CHECKPOINT_NAME = "decisions.yaml"


def link_pair(link: Mapping[str, Any]) -> SourcePair:
    """Return the canonical source pair named by a sealed link."""
    sources = link["sources"]
    return source_pair(str(sources[0]["source_sha256"]), str(sources[1]["source_sha256"]))


def read_checkpoint(
    path: Path,
    reviewer: str,
    links: list[Mapping[str, Any]],
    extra_pairs: frozenset[SourcePair] = frozenset(),
) -> dict[SourcePair, Decision]:
    """Read a checkpoint, refusing a changed reviewer or decisions outside the link record."""
    if path.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "review checkpoint is a symbolic link")
    if not path.exists():
        return {}
    review = read_decisions(path)
    if review.reviewer != reviewer:
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT, "review checkpoint names a different reviewer"
        )
    allowed = {link_pair(link) for link in links} | extra_pairs
    if any(pair not in allowed for pair in review.by_pair):
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT, "review checkpoint names a different link set"
        )
    return dict(review.by_pair)


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_checkpoint(path: Path, reviewer: str, decisions: Mapping[SourcePair, Decision]) -> None:
    """Atomically persist all decisions and synchronize the containing directory."""
    if path.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "review checkpoint is a symbolic link")
    rows: list[JsonValue] = []
    for pair, decision in sorted(decisions.items()):
        row: dict[str, JsonValue] = {"sources": list(pair), "decision": decision.decision}
        if decision.note is not None:
            row["note"] = decision.note
        rows.append(row)
    document: dict[str, JsonValue] = {"schema_version": 1, "reviewer": reviewer, "decisions": rows}
    payload = yaml.safe_dump(document, sort_keys=False, allow_unicode=False).encode("ascii")
    write_atomically(path, payload, mode=0o600)
    _sync_directory(path.parent)
