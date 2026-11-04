"""The dialect and the small schemas the dialect tests place a construct in."""

import json
from typing import Any

from tests.schema.conftest import CONTRACTS, contract_schema

DIALECT = json.loads((CONTRACTS / "meta" / "dialect.json").read_text(encoding="utf-8"))
ENCODED = "record"
NAME = {"type": "string", "description": "A name."}


def tagged_branch(tag: object, **properties: dict[str, object]) -> dict[str, Any]:
    fields = {
        "transform": {"type": "string", "const": tag, "description": "The tag."},
        **properties,
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(fields),
        "properties": fields,
    }


def with_property(node: dict[str, Any]) -> dict[str, Any]:
    return contract_schema(ENCODED, "test", "1.0.0", properties={"value": node})


OPEN = {"type": "object", "description": "Open.", "properties": {}}
CLOSED = {**OPEN, "additionalProperties": False}
