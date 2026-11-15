"""How a record of an earlier major is read: the change log's disposition, and its floor."""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.dispositions import PROTECTED_PROPERTIES, disposition_floor
from ss_track.schema.compatibility.evolution import diff_schemas, required_bump
from ss_track.schema.compatibility.freeze import freeze_contract
from ss_track.schema.registry.contract import FACTS, RETIRED, VIEW, version_key
from ss_track.schema.registry.fingerprints import walk
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.enforce import older_disposition, readable_majors

_CORPUS = "ss-track.corpus-manifest"
_SOURCE = "ss-track.source-manifest"
_BUNDLE = "ss-track.frame-bundle"


@pytest.mark.parametrize(
    ("kind", "found", "current", "disposition"),
    [
        (_SOURCE, 1, 3, FACTS),
        (_SOURCE, 2, 3, FACTS),
        (_CORPUS, 1, 3, RETIRED),
        (_CORPUS, 2, 3, RETIRED),
        (_BUNDLE, 1, 3, RETIRED),
        (_BUNDLE, 2, 3, RETIRED),
        (_CORPUS, 0, 3, None),
        (_CORPUS, 3, 3, None),
        ("ss-track.unknown", 1, 2, None),
    ],
)
def test_each_installed_older_major_has_its_stated_disposition(
    kind: str, found: int, current: int, disposition: str | None
) -> None:
    assert older_disposition(kind, found, current) == disposition


def test_no_installed_major_is_a_view_yet() -> None:
    assert readable_majors(_CORPUS, 3) == [3]
    assert readable_majors(_SOURCE, 3) == [3]


def test_a_transition_states_the_disposition_of_the_major_it_replaces() -> None:
    contract = load_contract_set().named("result/command")
    assert contract.disposition_of(0) is None  # every transition of this contract is a minor


def _streams_rights(extra: dict[str, Any]) -> dict[str, Any]:
    rights = {"type": "object", "properties": extra, "required": sorted(extra)}
    item = {"type": "object", "properties": {"rights": rights}, "required": ["rights"]}
    return {"type": "object", "properties": {"streams": {"type": "array", "items": item}}}


def test_a_major_adding_an_operator_judgment_floors_at_facts() -> None:
    old = _streams_rights({"basis": {"type": "string"}})
    new = _streams_rights({"basis": {"type": "string"}, "consent": {"type": "string"}})

    assert disposition_floor(diff_schemas(old, new), new) == FACTS


def test_a_major_retyping_a_case_transform_revision_floors_at_facts() -> None:
    """A transform revision is an algorithm revision, which section 17.4 says no view restates."""

    def cases(revision: dict[str, Any]) -> dict[str, Any]:
        case = {"type": "object", "properties": {"transform_revision": revision}}
        listed = {"type": "array", "items": case}
        return {"type": "object", "properties": {"generated_cases": listed}}

    old, new = cases({"type": "integer"}), cases({"type": "string"})

    assert disposition_floor(diff_schemas(old, new), new) == FACTS


def test_every_protected_name_is_a_property_an_installed_contract_states() -> None:
    """A protected name no contract states protects nothing, and usually means a rename was missed."""
    contracts = load_contract_set()
    stated = {
        name
        for contract in contracts.contracts
        for frozen in contract.versions
        for node in walk(contracts.frozen_schema(contract, frozen))
        for name in node.get("properties", {})
    }

    assert stated >= PROTECTED_PROPERTIES


def test_removing_a_judgment_or_adding_a_list_that_may_hold_one_needs_no_facts() -> None:
    old = _streams_rights({"basis": {"type": "string"}, "holder": {"type": "string"}})
    removed = _streams_rights({"basis": {"type": "string"}})
    cases = {"type": "array", "items": {"type": "object", "properties": {"split": {}}}}
    listed = old | {"properties": old["properties"] | {"cases": cases}, "required": ["cases"]}

    assert disposition_floor(diff_schemas(old, removed), removed) == VIEW
    assert disposition_floor(diff_schemas(old, listed), listed) == VIEW


def test_a_const_widened_to_an_enum_holding_it_is_one_minor_change() -> None:
    widened = diff_schemas({"const": "retired"}, {"enum": ["facts", "retired"]})
    replaced = diff_schemas({"const": "retired"}, {"enum": ["facts"]})

    assert [(item.pointer, item.bump) for item in widened] == [("/enum", "minor")]
    assert required_bump(replaced) == "major"


def _next_corpus_major(contract_root: Path, tmp_path: Path) -> Path:
    folder = contract_root / "record/corpus-manifest"
    chosen = max(folder.glob("3.*.json"), key=lambda path: version_key(path.stem))
    current = json.loads(chosen.read_bytes())
    current["$id"] = current["$id"].replace(f":{chosen.stem}", ":4.0.0")
    current["properties"]["schema_version"]["const"] = 4
    stream = current["properties"]["streams"]["items"]
    rights = stream["properties"]["rights"]
    rights["properties"]["consent"] = {"type": "string", "description": "Who consented."}
    rights["required"] = [*rights["required"], "consent"]
    path = tmp_path / "corpus-4.0.0.json"
    path.write_text(json.dumps(current))
    return path


def _freeze(root: Path, path: Path, disposition: str) -> None:
    freeze_contract(
        "record/corpus-manifest",
        path,
        root=root,
        summary="Require consent.",
        migration="State consent and build again.",
        disposition=disposition,
    )


def test_freeze_refuses_a_view_of_a_major_that_adds_an_operator_judgment(
    contract_root: Path, tmp_path: Path
) -> None:
    path = _next_corpus_major(contract_root, tmp_path)

    with pytest.raises(
        CorpusRefusal,
        match="changes an operator judgment or an algorithm revision, so its disposition is",
    ):
        _freeze(contract_root, path, VIEW)
    _freeze(contract_root, path, FACTS)

    contract = load_contract_set(contract_root).named("record/corpus-manifest")
    assert contract.disposition_of(3) == FACTS


@pytest.mark.parametrize("field", ["camera_control_mode", "observer_platform"])
def test_capture_judgments_cannot_be_derived_by_a_view(field: str) -> None:
    old = {"type": "object", "properties": {field: {"type": "number"}}}
    new = {"type": "object", "properties": {field: {"type": "string"}}}
    assert disposition_floor(diff_schemas(old, new), new) == FACTS
