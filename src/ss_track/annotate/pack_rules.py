"""Cross-field rules of a scenario pack. The contract names each one under ``x-rules``."""

from itertools import pairwise
from typing import NoReturn

from ss_track.annotate.pack_model import Envelope, ExtentBin, PackClass, Phase2, ScenarioPack
from ss_track.corpus.declarations.fields import invalid

RULES = (
    "class-ids",
    "class-parents",
    "extent-bins",
    "extent-order",
    "envelope-order",
    "envelope-classes",
    "phase2-classes",
    "stand-off-levels",
    "activity",
    "strata",
)


def check_scenario_pack(pack: ScenarioPack) -> None:
    """Refuse a pack that breaks a rule the schema cannot state."""
    _class_ids(pack)
    _parents(pack)
    _bins(pack.extent_bins)
    _extent_order(pack)
    _envelopes(pack)
    _phase2_rules(pack)
    _activity(pack)
    _strata(pack)


def _refuse(rule: str, message: str) -> NoReturn:
    raise invalid(f"{rule}: {message}")


def _duplicate(values: tuple[str, ...]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None


def _unique(rule: str, label: str, values: tuple[str, ...]) -> None:
    found = _duplicate(values)
    if found is not None:
        _refuse(rule, f"duplicate {label} {found}")


def _class_ids(pack: ScenarioPack) -> None:
    _unique("class-ids", "class id", tuple(item.class_id for item in pack.classes))


def _parents(pack: ScenarioPack) -> None:
    by_id = {item.class_id: item for item in pack.classes}
    for item in pack.classes:
        _parent_chain(item.class_id, item.parent_class_id, by_id)


def _parent_chain(start: str, parent: str | None, by_id: dict[str, PackClass]) -> None:
    seen: set[str] = set()
    current = parent
    while current is not None:
        if current == start or current in seen:
            _refuse("class-parents", f"{start} has a parent cycle")
        if current not in by_id:
            _refuse("class-parents", f"{start} names unknown parent {current}")
        seen.add(current)
        current = by_id[current].parent_class_id


def _bins(bins: tuple[ExtentBin, ...]) -> None:
    if not bins:
        return
    _unique("extent-bins", "bin id", tuple(item.bin_id for item in bins))
    for item in bins:
        if item.max_px is not None and item.max_px <= item.min_px:
            _refuse("extent-bins", f"bin {item.bin_id} is empty")
    _partition(tuple(sorted(bins, key=lambda item: item.min_px)))


def _partition(ordered: tuple[ExtentBin, ...]) -> None:
    if ordered[0].min_px != 0:
        _refuse("extent-bins", "extent bins must start at 0 px")
    if ordered[-1].max_px is not None:
        _refuse("extent-bins", "the last extent bin has an upper bound")
    for earlier, later in pairwise(ordered):
        _adjacent(earlier, later)


def _adjacent(earlier: ExtentBin, later: ExtentBin) -> None:
    upper = earlier.max_px
    if upper is None or upper > later.min_px:
        _refuse("extent-bins", f"bin {earlier.bin_id} overlaps {later.bin_id}")
    if upper < later.min_px:
        _refuse("extent-bins", f"extent bins leave a gap before {later.bin_id}")


def _extent_order(pack: ScenarioPack) -> None:
    box, point = pack.min_box_extent_px, pack.min_point_extent_px
    if box is not None and point is not None and point > box:
        _refuse("extent-order", "minimum point extent exceeds minimum box extent")


def _envelopes(pack: ScenarioPack) -> None:
    seen: set[str] = set()
    ids = {item.class_id for item in pack.classes}
    for envelope in pack.envelopes:
        _envelope_shape(envelope)
        _envelope_classes(envelope, ids, seen)


def _envelope_shape(envelope: Envelope) -> None:
    if envelope.d_alert_m < envelope.d_min_m:
        _refuse("envelope-order", "d_alert_m is below d_min_m")
    sectors = tuple(item.sector_id for item in envelope.approach_sectors)
    zones = tuple(item.zone_id for item in envelope.exclusion_zones)
    _unique("envelope-order", "sector", sectors)
    _unique("envelope-order", "zone", zones)
    _unique("envelope-order", "end condition", envelope.end_conditions)
    for sector in envelope.approach_sectors:
        if sector.elevation_min_deg > sector.elevation_max_deg:
            _refuse("envelope-order", f"sector {sector.sector_id} has inverted elevation")


def _envelope_classes(envelope: Envelope, ids: set[str], seen: set[str]) -> None:
    _unique("envelope-classes", "class id", envelope.class_ids)
    for class_id in envelope.class_ids:
        if class_id not in ids:
            _refuse("envelope-classes", f"unknown class id {class_id}")
        if class_id in seen:
            _refuse("envelope-classes", f"class {class_id} is in more than one envelope")
        seen.add(class_id)


def _phase2_rules(pack: ScenarioPack) -> None:
    phase2 = pack.phase2
    if phase2 is None:
        return
    ids = {item.class_id for item in pack.classes}
    _class_list("target_set", phase2.target_set, ids)
    _class_list("known_non_targets", phase2.known_non_targets, ids)
    _disjoint(phase2)
    _stand_off(phase2)


def _class_list(label: str, values: tuple[str, ...] | None, ids: set[str]) -> None:
    if values is None:
        return
    _unique("phase2-classes", f"class id in {label}", values)
    unknown = next((value for value in values if value not in ids), None)
    if unknown is not None:
        _refuse("phase2-classes", f"{label} names unknown class id {unknown}")


def _disjoint(phase2: Phase2) -> None:
    targets, others = phase2.target_set, phase2.known_non_targets
    if targets is None or others is None:
        return
    shared = set(targets) & set(others)
    if shared:
        _refuse("phase2-classes", f"class {min(shared)} is both a target and a known non-target")


def _stand_off(phase2: Phase2) -> None:
    levels = phase2.stand_off_levels_m
    if levels is not None and any(later <= earlier for earlier, later in pairwise(levels)):
        _refuse("stand-off-levels", "stand-off levels must increase")


def _activity(pack: ScenarioPack) -> None:
    _unique("activity", "activity", pack.vocabulary.activity)


def _strata(pack: ScenarioPack) -> None:
    _unique("strata", "stratum", pack.observer_platform_strata)
