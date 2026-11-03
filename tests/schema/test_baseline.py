"""The corpus baseline matches real bytes and rejects mixed transform parameters."""

import copy
from pathlib import Path
from typing import Any

import pytest

from ss_track.corpus.builder import CORPUS_MANIFEST
from ss_track.corpus.declaration import CORPUS_SCHEMA_VERSION
from ss_track.corpus.frames import FRAME_BUNDLE
from ss_track.corpus.host_hashes import STAGED_HASHES
from ss_track.corpus.transforms import TRANSFORM_REVISIONS
from ss_track.refusal import CorpusRefusal, RefusalCode
from ss_track.schema import validate_file
from ss_track.schema.fingerprints import walk
from ss_track.schema.store import load_contract_set
from ss_track.schema.strict import violations
from tests.schema.conftest import KEPT_FRAME_SET


def frozen(name: str) -> dict[str, Any]:
    contracts = load_contract_set()
    contract = contracts.named(name)
    return contracts.frozen_schema(contract, contract.versions[-1])


@pytest.mark.parametrize(
    "filename",
    [
        "source-schema-2-129a350.json",
        "corpus-schema-3-129a350.json",
        "bundle-schema-3-d6b704d.json",
        "frame-set-schema-1-fd982a1.json",
        "staged-hashes-schema-1-0bf3b9e.json",
        "hash-comparison-schema-1-0bf3b9e.json",
    ],
)
def test_retained_current_records_validate_unchanged(filename: str) -> None:
    path = KEPT_FRAME_SET.with_name(filename)
    before = path.read_bytes()
    assert validate_file(path).seal_checked
    assert path.read_bytes() == before


def test_corpus_three_before_source_terms_is_not_the_frozen_contract() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        validate_file(KEPT_FRAME_SET.with_name("corpus-schema-3-d6b704d.json"))
    assert caught.value.code is RefusalCode.RECORD_INVALID
    assert "rights" in str(caught.value.details)


@pytest.mark.parametrize("format", [CORPUS_MANIFEST, FRAME_BUNDLE, STAGED_HASHES])
def test_each_record_owns_its_major(format: Any) -> None:
    schema = frozen("record/" + format.kind.removeprefix("ss-track."))
    assert schema["properties"]["kind"]["const"] == format.kind
    assert schema["properties"]["schema_version"]["const"] == format.major


def test_corpus_declaration_major_and_refusal_codes_agree() -> None:
    assert (
        frozen("declaration/corpus")["properties"]["schema_version"]["const"]
        == CORPUS_SCHEMA_VERSION
    )
    assert set(frozen("result/command")["properties"]["code"]["enum"]) == {
        code.value for code in RefusalCode
    }


@pytest.mark.parametrize(
    ("contract", "definition"),
    [
        ("declaration/corpus", "recipe"),
        ("record/corpus-manifest", "case"),
        ("record/frame-bundle", "recipe"),
    ],
)
def test_every_transform_has_a_closed_branch(contract: str, definition: str) -> None:
    schema = frozen(contract)
    branches = schema["$defs"][definition]["oneOf"]
    assert {branch["properties"]["transform"]["const"] for branch in branches} == set(
        TRANSFORM_REVISIONS
    )
    registry = load_contract_set().schema_registry()
    for branch in branches:
        parameters = branch["properties"]["parameters"]
        assert parameters["additionalProperties"] is False
        assert violations({"another_transforms_parameter": 1}, parameters, registry)


def test_schema_alone_refuses_parameters_from_another_transform() -> None:
    schema = frozen("declaration/corpus")
    recipe_schema = schema | {"$ref": "#/$defs/recipe"}
    for field in ("type", "properties", "required", "additionalProperties"):
        recipe_schema.pop(field)
    good = {"case_id": "blurred", "transform": "blur", "seed": 1, "parameters": {"max_radius": 2}}
    registry = load_contract_set().schema_registry()
    assert not violations(good, recipe_schema, registry)
    wrong = copy.deepcopy(good)
    wrong["parameters"] = {"amplitude": 2}
    assert violations(wrong, recipe_schema, registry)


def _numeric_quantity(node: Any) -> bool:
    types = node.get("type", [])
    if isinstance(types, str):
        types = [types]
    return bool(set(types) & {"integer", "number"}) and "const" not in node


def test_all_numeric_quantities_and_color_codes_are_annotated() -> None:
    contracts = load_contract_set()
    for contract in contracts.contracts:
        for version in contract.versions:
            schema = contracts.frozen_schema(contract, version)
            for node in walk(schema):
                if _numeric_quantity(node):
                    assert "x-unit" in node, (contract.name, node)
    color = frozen("record/frame-bundle")["properties"]["color"]["properties"]
    assert all(node["x-vocabulary"].startswith("FFmpeg AV") for node in color.values())


def test_label_transform_kinds_are_tagged() -> None:
    branches = frozen("record/frame-bundle")["$defs"]["labels"]["oneOf"]
    assert {branch["properties"]["kind"]["const"] for branch in branches} == {
        "identity",
        "translate",
        "frame_map",
        "region_status",
    }


def test_every_frame_set_reference_resolves_at_its_pointer() -> None:
    contracts = load_contract_set()
    for node in walk(frozen("record/frame-set")):
        if "x-references" not in node:
            continue
        name, pointer = node["x-references"].split("#")
        contract = contracts.named(name)
        target = contracts.frozen_schema(contract, contract.versions[-1])
        for token in pointer.lstrip("/").split("/"):
            target = target[token.replace("~1", "/").replace("~0", "~")]
        assert target


def test_every_shipped_document_format_has_a_frozen_contract() -> None:
    contracts = load_contract_set()
    assert all(item.status == "active" and item.versions for item in contracts.contracts)


def test_examples_cover_every_frozen_document_contract() -> None:
    examples = Path(__file__).with_name("examples")
    contracts = load_contract_set()
    for contract in contracts.contracts:
        if contract.family == "shared" or not contract.versions:
            continue
        path = examples / f"{contract.family}-{contract.contract_id}.json"
        assert validate_file(path, contract_name=contract.name)
