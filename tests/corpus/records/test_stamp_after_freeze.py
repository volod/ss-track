"""A real in-place edit, re-pinned by `contracts freeze`, refuses a root stamped before it (spec 17.7)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.contract_stamp import require_current_data_root
from ss_track.core.evidence.stamp_file import REGENERATE_REMEDY
from ss_track.core.refusal import CorpusRefusal


def _edit_meaning(schema: dict[str, Any]) -> None:
    schema["properties"]["corpus_id"]["description"] = "Changed interpretation."


def _edit_structure(schema: dict[str, Any]) -> None:
    schema["properties"]["note"] = {"type": "string", "description": "An optional note."}


def _edit_shared(schema: dict[str, Any]) -> None:
    schema["$defs"]["note"] = {"type": "string", "description": "A shared note."}


@pytest.mark.parametrize(
    ("name", "edit", "structure_moves"),
    [
        pytest.param("record/frame-set", _edit_meaning, False, id="meaning"),
        pytest.param("record/frame-set", _edit_structure, True, id="structure"),
        pytest.param("shared/types", _edit_shared, True, id="shared"),
    ],
)
def test_a_real_freeze_stales_a_stamped_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    edit: Callable[[dict[str, Any]], None],
    structure_moves: bool,
) -> None:
    """Spec section 17.7: a structural, meaning-only or shared edit, re-pinned, refuses the root."""
    from ss_track.schema.compatibility.freeze import freeze_contract
    from ss_track.schema.registry.contract import version_path
    from ss_track.schema.registry.fingerprints import structure_fingerprint
    from ss_track.schema.registry.store import load_contract_set
    from ss_track.schema.validation import enforce
    from tests.schema.conftest import development_copy

    project = tmp_path / "project"
    project.mkdir()
    root = development_copy(project)
    monkeypatch.setattr(enforce, "load_contract_set", lambda: load_contract_set(root))
    enforce.installed_contracts.cache_clear()
    try:
        data = tmp_path / "data"
        require_current_data_root(data)
        contract_stamp.stamp_before_write(data / "record.json")
        schema = json.loads((root / version_path(name, "1.0.0")).read_bytes())
        original = structure_fingerprint(schema)
        edit(schema)
        candidate = tmp_path / "candidate.json"
        candidate.write_text(json.dumps(schema))
        freeze_contract(name, candidate, root=root, summary="Edit in place.")
        assert (structure_fingerprint(schema) != original) is structure_moves
        enforce.installed_contracts.cache_clear()
        with pytest.raises(CorpusRefusal) as caught:
            require_current_data_root(data)
        assert caught.value.details["changed_contracts"] == [name]
        assert caught.value.details["remedy"] == REGENERATE_REMEDY
    finally:
        enforce.installed_contracts.cache_clear()
