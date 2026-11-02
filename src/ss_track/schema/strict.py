"""The local validator: JSON Schema 2020-12, stricter than the standard where it is loose.

`1.0` is an integer to the standard, and `$` to Python's `re` also matches before a final newline,
which no ECMA-262 validator accepts. Without this, one record could pass here and fail elsewhere.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from itertools import islice
from typing import Any

from jsonschema import Draft202012Validator, ValidationError, validators
from jsonschema.protocols import Validator
from referencing import Registry

from ss_track.refusal import JsonValue

VIOLATION_LIMIT = 20
_END_ANCHOR = "$"
_POINTER_ESCAPES = (("~", "~0"), ("/", "~1"))

type Schema = dict[str, Any]


def _pattern(
    _: Validator, pattern: str, instance: object, schema: Mapping[str, object]
) -> Iterator[ValidationError]:
    """Apply `pattern` with `$` meaning the end of the value, as it does in ECMA-262."""
    if not isinstance(instance, str):
        return
    anchored = (
        pattern.removesuffix(_END_ANCHOR) + r"\Z" if pattern.endswith(_END_ANCHOR) else pattern
    )
    if re.search(anchored, instance) is None:
        yield ValidationError(f"{instance!r} does not match {schema['pattern']!r}")


StrictValidator = validators.extend(
    Draft202012Validator,
    validators={"pattern": _pattern},
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda _, value: type(value) is int
    ),
)


@dataclass(frozen=True, slots=True)
class Violation:
    """One way a document breaks a schema, named by JSON pointer."""

    pointer: str
    keyword: str
    message: str

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form a refusal reports."""
        return {"pointer": self.pointer, "keyword": self.keyword, "message": self.message}


def _pointer(error: ValidationError) -> str:
    parts = []
    for part in error.absolute_path:
        text = str(part)
        for raw, escaped in _POINTER_ESCAPES:
            text = text.replace(raw, escaped)
        parts.append(f"/{text}")
    return "".join(parts)


def violations(document: object, schema: Schema, registry: Registry[Any]) -> list[Violation]:
    """Return up to `VIOLATION_LIMIT` violations in one order, so one input gives one report."""
    validator = StrictValidator(
        schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    errors = islice(validator.iter_errors(document), VIOLATION_LIMIT)
    found = [Violation(_pointer(error), str(error.validator), error.message) for error in errors]
    return sorted(found, key=lambda item: (item.pointer, item.keyword, item.message))
