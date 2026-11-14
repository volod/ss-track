"""Shared evidence must not depend on an area, nor consumers on corpus internals."""

import ast
from collections.abc import Mapping
from importlib.util import resolve_name
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import JsonValue

ROOT = Path(__file__).resolve().parents[2] / "src" / "ss_track"
SHARED = ("core/evidence", "core/scratch.py", "core/clean.py", "core/clean_kinds.py")
OLD = (
    "ss_track.corpus.records.sealed",
    "ss_track.corpus.records.sealing",
    "ss_track.corpus.records.read_window",
    "ss_track.corpus.records.read_refusals",
    "ss_track.corpus.storage.scratch",
    "ss_track.corpus.storage.clean",
    "ss_track.corpus.storage.clean_kinds",
)


def imports(path: Path) -> list[str]:
    """List absolute imports, including names imported from packages."""
    result = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            package = "ss_track." + ".".join(path.relative_to(ROOT).parts[:-1])
            module = (
                resolve_name("." * node.level + (node.module or ""), package)
                if node.level
                else node.module or ""
            )
            result.append(module)
            result.extend(f"{module}.{alias.name}" for alias in node.names)
    return result


def test_shared_evidence_does_not_import_areas() -> None:
    paths = [
        p
        for entry in SHARED
        for p in ((ROOT / entry).rglob("*.py") if (ROOT / entry).is_dir() else [ROOT / entry])
    ]
    for path in paths:
        assert not [
            name
            for name in imports(path)
            if name.startswith("ss_track.")
            and not name.startswith(("ss_track.core", "ss_track.schema"))
        ], path


def test_other_areas_do_not_import_corpus_primitives() -> None:
    for path in ROOT.rglob("*.py"):
        if path.is_relative_to(ROOT / "corpus"):
            continue
        assert not [
            name
            for name in imports(path)
            if any(name == old or name.startswith(old + ".") for old in OLD)
        ], path


def test_projection_registration_refuses_replacement(monkeypatch: pytest.MonkeyPatch) -> None:
    """An area cannot silently replace another area's interpretation."""
    from ss_track.core.evidence import registry

    monkeypatch.setattr(registry, "PROJECTIONS", {})
    key = ("example", 1)

    def projection(record: Mapping[str, Any]) -> dict[str, JsonValue]:
        return dict(record)

    registry.register_projections({key: projection})
    with pytest.raises(ValueError, match="duplicate projections"):
        registry.register_projections({key: projection})
    assert registry.PROJECTIONS[key] is projection
