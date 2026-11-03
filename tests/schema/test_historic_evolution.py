"""Real historic records witness breaking shapes, without treating samples as full contracts.

Each of the five real bumps also replays to the disposition it warranted: three need only a view,
which derives no operator judgment, and two lack facts only an operator can state.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

import pytest
from referencing import Registry

from ss_track.corpus.read_window import View, apply_views, check_view, view_findings
from ss_track.refusal import JsonValue
from ss_track.schema.dispositions import disposition_floor
from ss_track.schema.evolution import diff_schemas, required_bump
from ss_track.schema.store import FACTS, VIEW
from ss_track.schema.strict import violations
from tests.corpus._historic import kept_record

type Upcast = Callable[[Mapping[str, JsonValue]], dict[str, JsonValue]]


def observed_shape(value: Any) -> dict[str, Any]:
    """Project observed keys and types only; omit values so changing a seal or stamp proves nothing."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {key: observed_shape(child) for key, child in value.items()},
            "required": sorted(value),
            "additionalProperties": False,
        }
    if isinstance(value, list):
        return {"type": "array", "items": observed_shape(value[0]) if value else {}}
    types = {str: "string", int: "integer", float: "number", bool: "boolean", type(None): "null"}
    return {"type": types[type(value)]}


@pytest.mark.parametrize(
    ("before", "after", "changed"),
    [
        ("corpus-schema-1-294535c", "corpus-schema-2-78db68c", "/properties/sequences"),
        ("bundle-schema-1-294535c", "bundle-schema-2-78db68c", "/properties/sequence_id"),
        ("corpus-schema-2-78db68c", "corpus-schema-3-d6b704d", "/properties/generated_cases"),
        ("bundle-schema-2-78db68c", "bundle-schema-3-d6b704d", "/properties/generated"),
        (
            "source-schema-1-d6b704d",
            "source-schema-2-129a350",
            "/properties/rights/properties/retain_until",
        ),
    ],
)
def test_all_five_real_bumps_are_major(before: str, after: str, changed: str) -> None:
    old, new = [observed_shape(json.loads(kept_record(name + ".json"))) for name in (before, after)]
    changes = diff_schemas(old, new)
    assert required_bump(changes) == "major"
    assert any(item.pointer == changed and item.bump == "major" for item in changes)
    assert not any(item.pointer.endswith(("schema_version", "manifest_sha256")) for item in changes)


def test_source_terms_added_without_a_bump_fail_the_previous_shape() -> None:
    old = json.loads(kept_record("corpus-schema-3-d6b704d.json"))
    new = json.loads(kept_record("corpus-schema-3-129a350.json"))
    assert old["schema_version"] == new["schema_version"] == 3
    found = violations(new, observed_shape(old), Registry())
    assert any(
        item.pointer == "/streams/0/rights" and item.keyword == "additionalProperties"
        for item in found
    )
    changes = diff_schemas(observed_shape(old), observed_shape(new))
    assert any(
        "/properties/rights/properties/retain_until" in item.pointer and item.bump == "major"
        for item in changes
    )


def _rename(old: str, new: str) -> Upcast:
    def upcast(record: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        renamed = {key: value for key, value in record.items() if key != old}
        return renamed | {new: record[old]}

    return upcast


def _sized_from(bundle: Mapping[str, Any]) -> Upcast:
    """Corpus 2 to 3, reading width and height from the bundle each stream pins."""

    def upcast(record: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        identity = bundle["identity"]
        streams = [
            dict(stream) | {"width": identity["width"], "height": identity["height"]}
            for stream in record["streams"]  # type: ignore[union-attr]
        ]
        return dict(record) | {"streams": streams, "generated_cases": []}

    return upcast


_VIEW_BUMPS = [
    pytest.param(
        "bundle-schema-1-294535c",
        "bundle-schema-2-78db68c",
        ("/stream_id",),
        _rename("sequence_id", "stream_id"),
        id="bundle-1-2",
    ),
    pytest.param(
        "bundle-schema-2-78db68c",
        "bundle-schema-3-d6b704d",
        ("/generated",),
        lambda record: dict(record) | {"generated": None},
        id="bundle-2-3",
    ),
    pytest.param(
        "corpus-schema-2-78db68c",
        "corpus-schema-3-d6b704d",
        ("/streams/*/width", "/streams/*/height", "/generated_cases"),
        _sized_from(json.loads(kept_record("bundle-schema-2-78db68c.json"))),
        id="corpus-2-3",
    ),
]


@pytest.mark.parametrize(("before", "after", "derived", "upcast"), _VIEW_BUMPS)
def test_three_real_bumps_replay_to_a_view(
    before: str, after: str, derived: tuple[str, ...], upcast: Upcast
) -> None:
    old, new = (json.loads(kept_record(name + ".json")) for name in (before, after))
    view = View(str(old["kind"]), int(old["schema_version"]), derived, upcast)

    assert disposition_floor(diff_schemas(observed_shape(old), observed_shape(new)), {}) == VIEW
    assert check_view(view, old) == []
    viewed = apply_views(old, {(view.kind, view.major): view}, view.major, view.major + 1)
    assert violations(viewed, observed_shape(new), Registry()) == []
    assert viewed["manifest_sha256"] == old["manifest_sha256"]


@pytest.mark.parametrize(
    ("before", "after", "judgment"),
    [
        ("corpus-schema-1-294535c", "corpus-schema-2-78db68c", "/streams/*/split"),
        ("source-schema-1-d6b704d", "source-schema-2-129a350", "/rights/retain_until"),
    ],
)
def test_two_real_bumps_replay_to_facts(before: str, after: str, judgment: str) -> None:
    old, new = (json.loads(kept_record(name + ".json")) for name in (before, after))
    changes = diff_schemas(observed_shape(old), observed_shape(new))
    view = View(str(old["kind"]), int(old["schema_version"]), (judgment,), dict)

    assert disposition_floor(changes, observed_shape(new)) == FACTS
    assert view_findings(view) != []
