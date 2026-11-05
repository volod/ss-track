"""A candidate document: each position in it, a copy with one value replaced, and "no witness"."""

import copy
from collections.abc import Callable, Iterator
from typing import Any

from tests.schema.compatibility._witness_node import Path

type Holds = Callable[[Any], bool]  # True when the strict validator confirms a break

NONE = object()  # what a search returns when it found no witness


def paths(value: Any, path: Path = ()) -> Iterator[Path]:
    """Yield every position in a JSON value, outermost first."""
    yield path
    if isinstance(value, dict):
        items: Iterator[tuple[Any, Any]] = iter(value.items())
    else:
        items = enumerate(value) if isinstance(value, list) else iter(())
    for key, item in items:
        yield from paths(item, (*path, key))


def at(document: Any, path: Path) -> Any:
    for key in path:
        document = document[key]
    return document


def replaced(document: Any, path: Path, value: Any) -> Any:
    """Return a copy of `document` with `value` at `path`."""
    if not path:
        return value
    result = copy.copy(document)
    result[path[0]] = replaced(document[path[0]], path[1:], value)
    return result
