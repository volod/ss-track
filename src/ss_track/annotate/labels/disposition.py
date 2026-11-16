"""How one labeled frame is reported. The result is never a numeric score.

The order is the rule. An unverifiable frame is ``unscorable``. A verifiable frame that is not a
primary localization frame is ``not_denominator``. ``fully_occluded``, ``out_of_view`` and
``absent`` are unlocalizable by the geometry rule, so those visibilities are decided before the
unlocalizable kind, or every such frame would be called unverifiable.
"""

from dataclasses import dataclass
from typing import Literal

DispositionStatus = Literal["scorable", "unscorable", "not_denominator"]
DISPOSITIONS = ("scorable", "unscorable", "not_denominator")
REASONS = (
    "identity_ambiguous",
    "unknown_mark",
    "ignore_region",
    "unknown",
    "fully_occluded",
    "out_of_view",
    "absent",
    "unlocalizable",
    "no_plausible_extent",
)
VISIBLE = frozenset({"visible", "partially_occluded"})  # the visibilities that carry an extent
WITHHELD = frozenset({"fully_occluded", "out_of_view", "absent"})  # verifiable, no extent


@dataclass(frozen=True, slots=True)
class Disposition:
    """The scoring status of one frame and the reason, when it has one."""

    status: DispositionStatus
    reason: str | None


def frame_disposition(
    *,
    identity: str,
    mark: str | None,
    visibility: str,
    kind: str,
    plausible_extent_px: int | None,
) -> Disposition:
    """Return the status of one frame. A scorable frame has no reason and no score."""
    if identity == "identity_ambiguous":
        return Disposition("unscorable", "identity_ambiguous")
    if mark == "unknown":
        return Disposition("unscorable", "unknown_mark")
    if mark == "ignore_region":
        return Disposition("not_denominator", "ignore_region")
    if visibility == "unknown":
        return Disposition("unscorable", "unknown")
    if visibility in WITHHELD:
        return Disposition("not_denominator", visibility)
    if kind == "unlocalizable":
        return Disposition("unscorable", "unlocalizable")
    if kind == "point_only" and plausible_extent_px is None:
        return Disposition("not_denominator", "no_plausible_extent")
    if visibility not in VISIBLE:
        raise TypeError(f"visibility {visibility} is not in the contract")
    return Disposition("scorable", None)
