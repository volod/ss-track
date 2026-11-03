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
_UNION = "oneOf"
_ABSENT = object()
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


def branch_tags(branch: Mapping[str, Any]) -> dict[str, object]:
    """Return the properties that identify one branch: required, with one fixed value."""
    required = branch.get("required", ())
    properties = branch.get("properties", {})
    return {
        name: child["const"]
        for name, child in properties.items()
        if name in required and "const" in child
    }


def union_tag(branches: list[dict[str, object]]) -> str | None:
    """Return a property that tells every branch from every other, if one exists."""
    shared = set(branches[0]).intersection(*branches[1:])
    for name in sorted(shared):
        values = [branch[name] for branch in branches]
        if all(values.count(value) == 1 for value in values):
            return name
    return None


def _tagging(error: ValidationError) -> tuple[dict[str, Any], list[dict[str, object]], str] | None:
    """Return the instance, branch tags and tag of a failed tagged union, or nothing."""
    branches, instance = error.validator_value, error.instance
    if error.validator != _UNION or not isinstance(branches, list):
        return None
    if not isinstance(instance, dict):
        return None
    tags = [branch_tags(branch) for branch in branches]
    tag = union_tag(tags)
    return None if tag is None else (instance, tags, tag)


def _unknown_tag(
    error: ValidationError, tags: list[dict[str, object]], tag: str, value: object
) -> ValidationError:
    if value is _ABSENT:
        return ValidationError(
            f"{tag!r} is a required property", validator=_UNION, path=[*error.absolute_path]
        )
    allowed = sorted(str(branch[tag]) for branch in tags)
    return ValidationError(
        f"{value!r} is not one of {allowed}",
        validator=_UNION,
        path=[*error.absolute_path, tag],
        instance=value,
    )


def _through_tag(error: ValidationError) -> Iterator[ValidationError]:
    """Report a tagged union through the branch its tag selects, not as a failure of every branch.

    Otherwise a wrong seed in one recipe reads as "not valid under any of the given schemas".
    """
    tagging = _tagging(error)
    if tagging is None:
        yield error
        return
    instance, tags, tag = tagging
    value = instance.get(tag, _ABSENT)
    chosen = [index for index, branch in enumerate(tags) if branch[tag] == value]
    if not chosen:
        yield _unknown_tag(error, tags, tag, value)
        return
    for item in error.context:
        if item.relative_schema_path[0] == chosen[0]:
            yield from _through_tag(item)


def violations(document: object, schema: Schema, registry: Registry[Any]) -> list[Violation]:
    """Return up to `VIOLATION_LIMIT` violations in one order, so one input gives one report."""
    validator = StrictValidator(
        schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    expanded = (item for error in validator.iter_errors(document) for item in _through_tag(error))
    errors = islice(expanded, VIOLATION_LIMIT)
    found = [Violation(_pointer(error), str(error.validator), error.message) for error in errors]
    return sorted(found, key=lambda item: (item.pointer, item.keyword, item.message))
