"""Two hashes, each moved by its own kind of edit and by nothing else."""

import copy
import json
from typing import Any

import pytest

from ss_track.schema.registry.fingerprints import meaning_fingerprint, structure_fingerprint
from tests.schema.conftest import CONTRACTS, contract_schema, frame_set_path


def _schema() -> dict[str, Any]:
    properties = {
        "title": {"type": "string", "description": "A property named title."},
        "description": {"type": "string", "description": "A property named description."},
        "mode": {"type": "string", "enum": ["a", "b"], "description": "A mode."},
        "size": {"type": "integer", "minimum": 0, "description": "A size.", "x-unit": "By"},
    }
    return contract_schema("record", "test", "1.0.0", properties=properties, required=["title"])


def _moved(change: Any) -> tuple[bool, bool]:
    before = _schema()
    after = copy.deepcopy(before)
    change(after)
    return (
        structure_fingerprint(before) != structure_fingerprint(after),
        meaning_fingerprint(before) != meaning_fingerprint(after),
    )


def _set(path: tuple[str, ...], value: object) -> Any:
    def change(schema: dict[str, Any]) -> None:
        node = schema
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return change


_PROPERTY_SIZE = ("properties", "size")


@pytest.mark.parametrize(
    ("change", "structure", "meaning"),
    [
        pytest.param(_set(("title",), "Other"), False, True, id="root title"),
        pytest.param(_set(("description",), "Other"), False, True, id="root description"),
        pytest.param(_set(("x-rules",), {"a": "b"}), False, True, id="rule"),
        pytest.param(_set((*_PROPERTY_SIZE, "x-unit"), "kBy"), False, True, id="unit"),
        pytest.param(
            _set((*_PROPERTY_SIZE, "description"), "Other"), False, True, id="description"
        ),
        pytest.param(_set((*_PROPERTY_SIZE, "examples"), [1]), False, True, id="example"),
        pytest.param(_set((*_PROPERTY_SIZE, "minimum"), 1), True, False, id="bound"),
        pytest.param(_set(("required",), ["mode"]), True, False, id="required"),
        pytest.param(_set(("properties", "mode", "enum"), ["a", "c"]), True, True, id="enum"),
        pytest.param(
            _set(("properties", "new"), {"type": "string", "description": "A."}),
            True,
            True,
            id="new property",
        ),
        pytest.param(
            _set(("$id",), "urn:ss-track:contract:record:test:1.1.0"), False, False, id="id"
        ),
    ],
)
def test_each_edit_moves_its_own_fingerprint(change: Any, structure: bool, meaning: bool) -> None:
    assert _moved(change) == (structure, meaning)


@pytest.mark.parametrize("name", ["title", "description"])
def test_a_property_named_like_an_annotation_stays_a_property(name: str) -> None:
    assert _moved(_set(("properties", name, "type"), "integer")) == (True, False)
    assert _moved(_set(("properties", name, "description"), "Other")) == (False, True)


def test_a_definition_with_no_annotation_moves_only_structure() -> None:
    assert _moved(_set(("$defs",), {"plain": {"type": "string"}})) == (True, False)


def test_formatting_and_key_order_move_neither() -> None:
    schema = _schema()
    reordered = json.loads(json.dumps(schema, indent=4, sort_keys=True))

    assert structure_fingerprint(schema) == structure_fingerprint(reordered)
    assert meaning_fingerprint(schema) == meaning_fingerprint(reordered)


def test_the_two_fingerprints_of_one_schema_differ() -> None:
    schema = json.loads(frame_set_path(CONTRACTS).read_text(encoding="utf-8"))

    assert structure_fingerprint(schema) != meaning_fingerprint(schema)


def test_a_union_branch_is_walked() -> None:
    branch = {
        "type": "object",
        "additionalProperties": False,
        "required": ["tag"],
        "properties": {"tag": {"type": "string", "const": "a", "description": "A tag."}},
    }
    schema = _schema()
    schema["properties"]["union"] = {"oneOf": [branch], "description": "A."}
    edited = copy.deepcopy(schema)
    edited["properties"]["union"]["oneOf"][0]["properties"]["tag"]["description"] = "Other."

    assert structure_fingerprint(schema) == structure_fingerprint(edited)
    assert meaning_fingerprint(schema) != meaning_fingerprint(edited)
