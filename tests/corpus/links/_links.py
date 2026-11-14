"""Shared shapes for the link tests: streams as a manifest states them, and a decisions file."""

from pathlib import Path

import yaml

A, B, C, D = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)


def stream(
    stream_id: str, source: str, group_id: str, split: str = "development"
) -> dict[str, str]:
    """Return a corpus stream with only what a link review reads."""
    return {"stream_id": stream_id, "source_sha256": source, "group_id": group_id, "split": split}


def write_decisions(path: Path, *decisions: dict[str, object], reviewer: str = "reviewer") -> Path:
    """Write a decisions file holding the given entries."""
    document = {"schema_version": 1, "reviewer": reviewer, "decisions": list(decisions)}
    path.write_text(yaml.safe_dump(document), encoding="ascii")
    return path


def decided(first: str, second: str, decision: str, **fields: object) -> dict[str, object]:
    """Return one decision entry."""
    return {"sources": [first, second], "decision": decision, **fields}
