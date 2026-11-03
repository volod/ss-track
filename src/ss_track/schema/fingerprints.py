"""Two hashes of what a contract states, independent of its formatting.

`structure` covers what a validator acts on, and `meaning` covers what a reader is told, plus the
values of `const` and `enum`. The walk follows schema positions because a property may be named
`title` or `description`, and that key is a name there and not an annotation.
"""

from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from ss_track.canonical import canonical_json, sha256_bytes
from ss_track.schema.strict import Schema

_NAMED_SCHEMAS = ("properties", "$defs")
_LISTED_SCHEMAS = ("oneOf", "prefixItems")
_SINGLE_SCHEMAS = ("items",)
_IDENTITY = {"$id", "$schema"}
_ANNOTATIONS = {"title", "description", "examples"}
_ANNOTATION_PREFIX = "x-"
_MEANING_VALUES = {"const", "enum"}

type Keep = Callable[[str], bool]


def subschemas(node: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Yield the schemas directly inside one schema, and nothing that only looks like one."""
    for keyword in _NAMED_SCHEMAS:
        yield from node.get(keyword, {}).values()
    for keyword in _LISTED_SCHEMAS:
        yield from node.get(keyword, ())
    for keyword in _SINGLE_SCHEMAS:
        if keyword in node and isinstance(node[keyword], Mapping):
            yield node[keyword]


def walk(node: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Yield a schema and every schema inside it."""
    yield node
    for child in subschemas(node):
        yield from walk(child)


def _is_annotation(keyword: str) -> bool:
    return keyword in _ANNOTATIONS or keyword.startswith(_ANNOTATION_PREFIX)


def _is_structure(keyword: str) -> bool:
    return keyword not in _IDENTITY and not _is_annotation(keyword)


def _is_meaning(keyword: str) -> bool:
    return _is_annotation(keyword) or keyword in _MEANING_VALUES


def _named(children: Mapping[str, Mapping[str, Any]], keep: Keep) -> Schema:
    projected = {name: _project(child, keep) for name, child in children.items()}
    return {name: child for name, child in projected.items() if child}


def _listed(children: Iterable[Mapping[str, Any]], keep: Keep) -> list[Schema]:
    return [_project(child, keep) for child in children]


def _project(node: Mapping[str, Any], keep: Keep) -> Schema:
    """Keep the chosen keywords at every schema position, dropping what ends up empty."""
    kept: Schema = {key: value for key, value in node.items() if key not in _WALKED and keep(key)}
    kept |= {
        keyword: _WALKED[keyword](node[keyword], keep) for keyword in _WALKED if keyword in node
    }
    return {key: value for key, value in kept.items() if value != {}}


def _single(node: Mapping[str, Any] | bool, keep: Keep) -> Schema | bool:
    if isinstance(node, bool):
        return node if keep("type") else {}
    return _project(node, keep)


_WALKED: dict[str, Callable[[Any, Keep], object]] = {
    "properties": _named,
    "$defs": _named,
    "oneOf": _listed,
    "prefixItems": _listed,
    "items": _single,
}


def structure_fingerprint(schema: Mapping[str, Any]) -> str:
    """Hash the schema without its annotations or its own version."""
    return sha256_bytes(canonical_json(_project(schema, _is_structure)))


def meaning_fingerprint(schema: Mapping[str, Any]) -> str:
    """Hash the annotations and the enumerated values, each at its own position."""
    return sha256_bytes(canonical_json(_project(schema, _is_meaning)))
