"""A synthetic next major of a real contract, frozen by the real freeze and installed for one test.

No real format has a successor major yet, so these tests give one: the shipped contract plus one
required property, frozen with a disposition, while the records stay the ones today's code writes.
Readers then read today's major as the older one, which is the case every later major will meet.
"""

import json
import shutil
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from ss_track.corpus import builder, read_window
from ss_track.corpus import projections as projection_table
from ss_track.corpus.builder import CORPUS_MANIFEST
from ss_track.corpus.read_window import View
from ss_track.corpus.sealed import RecordFormat
from ss_track.refusal import JsonValue
from ss_track.schema import enforce, store
from ss_track.schema.freeze import freeze_contract

CORPUS_CONTRACT = "record/corpus-manifest"
CURRENT = CORPUS_MANIFEST.major
NEXT = CURRENT + 1
_CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"

type Upcast = Callable[[Mapping[str, JsonValue]], dict[str, JsonValue]]


def candidate(root: Path, added: str, schema: Mapping[str, Any]) -> Path:
    """Write the shipped corpus contract at the next major, requiring one more property."""
    current = json.loads((root / "record" / "corpus-manifest" / f"{CURRENT}.0.0.json").read_bytes())
    current["$id"] = current["$id"].replace(f":{CURRENT}.0.0", f":{NEXT}.0.0")
    current["properties"]["schema_version"]["const"] = NEXT
    current["properties"][added] = dict(schema)
    current["required"] = [*current["required"], added]
    path = root.parent / f"corpus-manifest-{NEXT}.0.0.json"
    path.write_text(json.dumps(current, indent=2), encoding="ascii")
    return path


def freeze_next(root: Path, disposition: str, added: str, schema: Mapping[str, Any]) -> None:
    """Freeze the next corpus major in a private copy of the set, as an author would."""
    freeze_contract(
        CORPUS_CONTRACT,
        candidate(root, added, schema),
        root=root,
        summary="A synthetic next major.",
        migration="Read it through its disposition.",
        disposition=disposition,
    )


def private_contracts(directory: Path) -> Path:
    root = directory / "contracts"
    shutil.copytree(_CONTRACTS, root, ignore=shutil.ignore_patterns("__pycache__"))
    root.joinpath("__init__.py").unlink()
    return root


@contextmanager
def installed(root: Path) -> Iterator[None]:
    """Make a contract set the installed one, and the shipped one again afterwards."""
    shipped = store.default_root
    store.default_root = lambda: root
    enforce._installed.cache_clear()
    try:
        yield
    finally:
        store.default_root = shipped
        enforce._installed.cache_clear()


def read_as_next(
    monkeypatch: pytest.MonkeyPatch, upcast: Upcast | None = None, **view: Any
) -> None:
    """Have the corpus readers read the next major, with a view of today's one when given."""
    kind = CORPUS_MANIFEST.kind
    monkeypatch.setattr(builder, "CORPUS_MANIFEST", RecordFormat(kind, NEXT))
    projected = projection_table.installed_projections()[(kind, CURRENT)]
    monkeypatch.setitem(projection_table._PROJECTIONS, (kind, NEXT), projected)
    if upcast is not None:
        derived = tuple(view.get("derived", ()))
        monkeypatch.setitem(
            read_window._VIEWS, (kind, CURRENT), View(kind, CURRENT, derived, upcast)
        )
