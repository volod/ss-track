"""Shrink a confirmed witness until no single value can become simpler, so it names one fact."""

import json
from collections.abc import Iterator
from typing import Any

from tests.schema.compatibility._witness_document import NONE, Holds, at, paths, replaced
from tests.schema.compatibility._witness_node import SIMPLEST


def _simpler(value: Any) -> Iterator[Any]:
    yield from SIMPLEST
    if isinstance(value, str | list):
        for index in range(len(value)):
            yield value[:index] + value[index + 1 :]
    if isinstance(value, dict):
        yield from value.values()
        for key in value:
            yield {name: item for name, item in value.items() if name != key}
    if isinstance(value, list):
        yield from value


def _size(value: Any) -> int:
    return len(json.dumps(value))


def _smaller(document: Any, holds: Holds) -> Any:
    for path in paths(document):
        current = at(document, path)
        for candidate in _simpler(current):
            if _size(candidate) < _size(current):
                trial = replaced(document, path, candidate)
                if holds(trial):
                    return trial
    return NONE


def shrunk(document: Any, holds: Holds) -> Any:
    """Shrink a witness until no single value can become simpler, so it names one fact."""
    while (smaller := _smaller(document, holds)) is not NONE:
        document = smaller
    return document
