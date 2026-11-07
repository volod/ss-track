"""Damage the golden discovery bodies, and read what a refusal of them names."""

from collections.abc import Callable
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from tests.corpus.discovery._records import SIBLING_ID, Bodies, synthetic_bodies

type Damage = Callable[[Bodies], None]


def refused(damage: Damage) -> CorpusRefusal:
    """Seal damaged golden bodies, which must be `RECORD_INVALID` with nothing sealed."""
    bodies = synthetic_bodies()
    damage(bodies)
    with pytest.raises(CorpusRefusal) as caught:
        bodies.seal()
    assert caught.value.code is RefusalCode.RECORD_INVALID
    return caught.value


def findings(refusal: CorpusRefusal) -> list[dict[str, Any]]:
    found: Any = refusal.details["findings"]
    return list(found)


def rules(refusal: CorpusRefusal) -> set[str]:
    return {finding["rule"] for finding in findings(refusal)}


def one(bodies: Bodies) -> dict[str, Any]:
    return bodies.inventory("one")


def sibling(bodies: Bodies) -> dict[str, Any]:
    return bodies.candidate("one", SIBLING_ID)


def extractor(bodies: Bodies) -> dict[str, Any]:
    found: dict[str, Any] = bodies.run["extractors"][0]
    return found


def drop(path: str) -> Damage:
    """Remove one field, named by its path from a stream's inventory or from the run."""
    record, *keys = path.split(".")

    def damage(bodies: Bodies) -> None:
        node: Any = bodies.run if record == "run" else one(bodies)
        for key in keys[:-1]:
            node = node[int(key)] if key.isdigit() else node[key]
        del node[keys[-1]]

    return damage


def set_to(where: Callable[[Bodies], dict[str, Any]], **values: Any) -> Damage:
    def damage(bodies: Bodies) -> None:
        where(bodies).update(values)

    return damage


def selection(stream_id: str, candidate_id: str, **values: Any) -> Damage:
    return set_to(lambda b: b.candidate(stream_id, candidate_id)["selection"], **values)


def audit(stream_id: str, candidate_id: str, **values: Any) -> Damage:
    return set_to(lambda b: b.candidate(stream_id, candidate_id)["audit"], **values)
