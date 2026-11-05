"""Public projection keeps only values a contract marks public."""

from typing import Any

from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.views.disclosure import project_public

_URI = "urn:test:disclosure"


def _project(value: dict[str, Any], schema: dict[str, Any]) -> Any:
    resource = Resource.from_contents(schema, default_specification=DRAFT202012)
    registry = Registry().with_resource(_URI, resource)
    return project_public(value, schema, registry, _URI)


def test_unmarked_restricted_and_nested_values_stay_absent() -> None:
    schema = {
        "type": "object",
        "properties": {
            "basis": {"type": "string", "x-sensitivity": "public"},
            "retain_until": {"type": ["string", "null"], "x-sensitivity": "public"},
            "derived_frames": {"type": "boolean", "x-sensitivity": "public"},
            "sha256_declared": {"type": "boolean"},
            "source_sha256": {"type": "string", "x-sensitivity": "restricted"},
            "capture": {
                "type": "object",
                "x-sensitivity": "sensitive",
                "properties": {"camera": {"type": "string", "x-sensitivity": "public"}},
            },
            "rights": {
                "type": "object",
                "properties": {"sharing": {"type": "string", "x-sensitivity": "public"}},
            },
        },
    }
    projected = _project(
        {
            "basis": "owned",
            "retain_until": None,
            "derived_frames": False,
            "sha256_declared": True,
            "source_sha256": "ab" * 32,
            "capture": {"camera": "hidden-camera"},
            "rights": {"sharing": "public"},
        },
        schema,
    )
    assert projected == {
        "basis": "owned",
        "retain_until": None,
        "derived_frames": False,
        "rights": {"sharing": "public"},
    }


def test_tagged_recipe_keeps_scalar_parameters_and_drops_a_region() -> None:
    schema = {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "transform": {"const": "blur", "type": "string", "x-sensitivity": "public"},
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_radius": {"type": "integer", "x-sensitivity": "public"},
                            "region": {
                                "type": "object",
                                "x-sensitivity": "restricted",
                                "properties": {"x": {"type": "integer", "x-sensitivity": "public"}},
                            },
                        },
                    },
                },
                "required": ["transform"],
            }
        ]
    }
    projected = _project(
        {"transform": "blur", "parameters": {"max_radius": 17, "region": {"x": 4}}},
        schema,
    )
    assert projected == {"transform": "blur", "parameters": {"max_radius": 17}}


def test_frozen_recipe_publishes_scalar_parameters_only() -> None:
    contracts = load_contract_set()
    contract = contracts.named("record/frame-bundle")
    version = contract.newest()
    assert version is not None
    schema = contracts.frozen_schema(contract, version)["$defs"]["recipe"]
    projected = project_public(
        {
            "transform": "target_absence",
            "transform_revision": 1,
            "seed": 3,
            "window": {"start_frame": 0, "end_frame": 2},
            "parameters": {
                "region": {"x": 9, "y": 8, "width": 7, "height": 6},
                "plate_frame": 3,
                "noise": 4,
            },
        },
        schema,
        contracts.schema_registry(),
        contract.urn(version),
    )
    assert projected["parameters"] == {"plate_frame": 3, "noise": 4}
    assert projected["transform"] == "target_absence"
    assert projected["window"] == {"start_frame": 0, "end_frame": 2}
    assert "x" not in str(projected)
