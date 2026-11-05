"""Seal a record without its contract, as a damaged but self-consistent record would be sealed."""

from collections.abc import Mapping

from ss_track.core.canonical import SEAL_FIELD, seal_of
from ss_track.core.refusal import JsonValue


def self_sealed(body: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Return a record whose seal holds although no writer could have produced it.

    Production `seal` refuses a record its contract refuses, so a fixture of what a reader must
    refuse is sealed here instead.
    """
    return dict(body) | {SEAL_FIELD: seal_of(body)}
