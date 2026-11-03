"""Local keyword rules for the restricted dialect, independent of the oracle."""

import json
import re
from typing import Any

from ss_track.schema._patterns import covers, parse

PATCH = "patch"
MINOR = "minor"
MAJOR = "major"
RANK = {"none": 0, PATCH: 1, MINOR: 2, MAJOR: 3}
ANNOTATIONS = {"title", "description", "examples"}
MEANING = {"x-unit", "x-clock", "x-frame", "x-quantity", "x-vocabulary"}
_SENSITIVITY = {"public": 0, "restricted": 1, "sensitive": 2}
_LOWER_BOUNDS = {"minimum", "exclusiveMinimum", "minItems", "minLength"}
_UPPER_BOUNDS = {"maximum", "exclusiveMaximum", "maxItems", "maxLength"}
_MISSING = object()


def _types(value: Any) -> set[str]:
    result = set(value if isinstance(value, list) else [value])
    if "number" in result:
        result.add("integer")
    return result


def pattern_relaxed(old: str, new: str) -> bool:
    """Return true only for proven inclusion; unsupported rewrites conservatively need a major."""
    before, after = parse(old), parse(new)
    if before is not None and after is not None and covers(after, before):
        return True
    if re.fullmatch(r"\^[a-zA-Z0-9 _/-]+\$", old):
        return re.fullmatch(new.removeprefix("^").removesuffix("$"), old[1:-1]) is not None
    return False


def _annotation_class(keyword: str, old: Any, new: Any) -> str:
    if keyword in ANNOTATIONS:
        return PATCH
    if old is _MISSING:
        return MINOR
    if keyword == "x-sensitivity" and new is not _MISSING:
        return MINOR if _SENSITIVITY[new] > _SENSITIVITY[old] else MAJOR
    return MAJOR


def _bound_class(keyword: str, old: Any, new: Any) -> str:
    if old is _MISSING:
        return MAJOR
    if new is _MISSING:
        return MINOR
    relaxed = new < old if keyword in _LOWER_BOUNDS else new > old
    return MINOR if relaxed else MAJOR


def _constraint_class(keyword: str, old: Any, new: Any) -> str:
    if new is _MISSING:
        return MINOR
    if old is _MISSING:
        return MAJOR
    if keyword == "enum":
        before = {json.dumps(value, sort_keys=True) for value in old}
        after = {json.dumps(value, sort_keys=True) for value in new}
        return MINOR if before <= after else MAJOR
    if keyword == "pattern":
        return MINOR if pattern_relaxed(old, new) else MAJOR
    return MAJOR


def keyword_class(keyword: str, before: dict[str, Any], after: dict[str, Any]) -> str:
    """Classify one changed scalar keyword; unknown rules fail closed."""
    old, new = before.get(keyword, _MISSING), after.get(keyword, _MISSING)
    if keyword in ANNOTATIONS or keyword.startswith("x-"):
        return _annotation_class(keyword, old, new)
    if keyword in _LOWER_BOUNDS | _UPPER_BOUNDS:
        return _bound_class(keyword, old, new)
    if keyword in {"pattern", "format", "enum", "const"}:
        return _constraint_class(keyword, old, new)
    if keyword == "type":
        return MINOR if _types(old) <= _types(new) else MAJOR
    if keyword == "additionalProperties" and new is True:
        return MINOR
    return MAJOR
