"""The annotate subpackages import in one direction, and none imports the command layer.

A lower layer states a rule once and a higher one uses it. `validation` and `review` are
siblings: neither reads the other, so a change to review cannot break validation.
"""

from pathlib import Path

import pytest

from tests.core.test_evidence_boundaries import ROOT, imports

_PACKAGE = "ss_track.annotate"
_ALLOWED = {
    "declarations": (),
    "sources": ("declarations",),
    "packs": ("declarations",),
    "labels": ("declarations", "sources", "packs"),
    "validation": ("declarations", "sources", "packs", "labels"),
    "review": ("declarations", "sources", "packs", "labels"),
    "derivation": ("declarations", "sources", "packs", "labels", "review"),
}


def _modules(layer: str) -> list[Path]:
    return sorted((ROOT / "annotate" / layer).glob("*.py"))


def test_every_subpackage_is_a_declared_layer() -> None:
    found = {path.name for path in (ROOT / "annotate").iterdir() if path.is_dir()}
    assert found - {"__pycache__"} == set(_ALLOWED)
    assert [path.name for path in (ROOT / "annotate").glob("*.py")] == ["__init__.py"]


@pytest.mark.parametrize("layer", sorted(_ALLOWED))
def test_a_layer_imports_only_the_layers_below_it(layer: str) -> None:
    allowed = (layer, *_ALLOWED[layer])
    for path in _modules(layer):
        for name in imports(path):
            if not name.startswith(f"{_PACKAGE}."):
                continue
            other = name.removeprefix(f"{_PACKAGE}.").split(".")[0]
            assert other in allowed, f"{path.name} imports {name}"


def test_no_layer_imports_a_command() -> None:
    for layer in _ALLOWED:
        for path in _modules(layer):
            assert not [name for name in imports(path) if name.startswith("ss_track.commands")], (
                path
            )
