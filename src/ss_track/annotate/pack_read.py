"""Read a scenario pack whose contract has already accepted the document."""

from typing import cast

from ss_track.annotate.pack_model import (
    CLASS_ROLES,
    ENVELOPE_KINDS,
    ApproachSector,
    Approval,
    ClassRole,
    Envelope,
    EnvelopeKind,
    ExclusionZone,
    ExtentBin,
    PackClass,
    Phase2,
    ScenarioPack,
    Vocabulary,
)
from ss_track.corpus.declarations.fields import Fields


def read_pack(fields: Fields, pack_hash: str) -> ScenarioPack:
    """Return the typed pack. Cross-field rules are applied by the caller."""
    box, point, bins = _limits(fields)
    return ScenarioPack(
        pack_id=fields.string("pack_id"),
        schema_version=fields.index("schema_version"),
        classes=_classes(fields),
        vocabulary=_vocabulary(fields),
        min_box_extent_px=box,
        min_point_extent_px=point,
        extent_bins=bins,
        observer_platform_strata=_strings(fields, "observer_platform_strata"),
        access_policy=_access(fields),
        envelopes=_envelopes(fields),
        phase2=_phase2(fields),
        pack_hash=pack_hash,
    )


def _classes(fields: Fields) -> tuple[PackClass, ...]:
    found = []
    for index, raw in enumerate(fields.items("classes")):
        item = Fields(raw, f"{fields.where}.classes[{index}]")
        found.append(
            PackClass(
                class_id=item.string("class_id"),
                name=item.text("name"),
                role=_role(item.string("role")),
                parent_class_id=item.nullable_text("parent_class_id"),
                min_identifiable_extent_px=_optional_index(item, "min_identifiable_extent_px"),
            )
        )
    return tuple(found)


def _vocabulary(fields: Fields) -> Vocabulary:
    item = fields.child("vocabulary")
    return Vocabulary(
        visibility=_strings(item, "visibility"),
        geometry=_strings(item, "geometry"),
        camera_motion=_strings(item, "camera_motion"),
        non_scoring_mark=_strings(item, "non_scoring_mark"),
        activity=_strings(item, "activity"),
    )


def _limits(fields: Fields) -> tuple[int | None, int | None, tuple[ExtentBin, ...]]:
    item = fields.child("limits")
    return (
        item.nullable_index("min_box_extent_px"),
        item.nullable_index("min_point_extent_px"),
        _bins(item),
    )


def _bins(fields: Fields) -> tuple[ExtentBin, ...]:
    found = []
    for index, raw in enumerate(fields.items("extent_bins")):
        item = Fields(raw, f"{fields.where}.extent_bins[{index}]")
        found.append(
            ExtentBin(
                bin_id=item.string("bin_id"),
                min_px=item.index("min_px"),
                max_px=item.nullable_index("max_px"),
            )
        )
    return tuple(found)


def _access(fields: Fields) -> Approval | None:
    if not fields.has("access_policy"):
        return None
    return _approval(fields.child("access_policy"))


def _envelopes(fields: Fields) -> tuple[Envelope, ...]:
    if not fields.has("non_disturbance_envelopes"):
        return ()
    found = []
    key = "non_disturbance_envelopes"
    for index, raw in enumerate(fields.items(key)):
        found.append(_envelope(Fields(raw, f"{fields.where}.{key}[{index}]")))
    return tuple(found)


def _envelope(fields: Fields) -> Envelope:
    return Envelope(
        kind=_kind(fields.string("kind")),
        approval=_approval(fields),
        class_ids=_optional_strings(fields, "class_ids") or (),
        d_min_m=fields.number("d_min_m"),
        d_alert_m=fields.number("d_alert_m"),
        v_close_max_m_s=fields.number("v_close_max_m_s"),
        approach_sectors=_sectors(fields),
        exclusion_zones=_zones(fields),
        t_follow_max_s=fields.number("t_follow_max_s"),
        end_conditions=_strings(fields, "end_conditions"),
    )


def _sectors(fields: Fields) -> tuple[ApproachSector, ...]:
    found = []
    for index, raw in enumerate(fields.items("approach_sectors")):
        item = Fields(raw, f"{fields.where}.approach_sectors[{index}]")
        found.append(
            ApproachSector(
                sector_id=item.string("sector_id"),
                bearing_start_deg=item.number("bearing_start_deg"),
                bearing_end_deg=item.number("bearing_end_deg"),
                elevation_min_deg=item.number("elevation_min_deg"),
                elevation_max_deg=item.number("elevation_max_deg"),
            )
        )
    return tuple(found)


def _zones(fields: Fields) -> tuple[ExclusionZone, ...]:
    found = []
    for index, raw in enumerate(fields.items("exclusion_zones")):
        item = Fields(raw, f"{fields.where}.exclusion_zones[{index}]")
        found.append(
            ExclusionZone(
                zone_id=item.string("zone_id"),
                radius_m=item.number("radius_m"),
                height_m=item.number("height_m"),
            )
        )
    return tuple(found)


def _phase2(fields: Fields) -> Phase2 | None:
    if not fields.has("phase2"):
        return None
    item = fields.child("phase2")
    return Phase2(
        target_set=_optional_strings(item, "target_set"),
        known_non_targets=_optional_strings(item, "known_non_targets"),
        unknown_set=item.boolean("unknown_set") if item.has("unknown_set") else None,
        identifiable_duration_s=_optional_number(item, "identifiable_duration_s"),
        declaration_deadline_s=_optional_number(item, "declaration_deadline_s"),
        declaration_burden_per_hour=_optional_number(item, "declaration_burden_per_hour"),
        target_size_m=_optional_number(item, "target_size_m"),
        stand_off_levels_m=_optional_numbers(item, "stand_off_levels_m"),
    )


def _approval(fields: Fields) -> Approval:
    item = fields.child("approval")
    return Approval(owner=item.text("owner"), reference=item.text("reference"))


def _strings(fields: Fields, key: str) -> tuple[str, ...]:
    found = []
    for item in fields.items(key):
        if not isinstance(item, str):
            raise TypeError(f"{fields.where}.{key} is not a string list")
        found.append(item)
    return tuple(found)


def _optional_strings(fields: Fields, key: str) -> tuple[str, ...] | None:
    return _strings(fields, key) if fields.has(key) else None


def _optional_index(fields: Fields, key: str) -> int | None:
    return fields.index(key) if fields.has(key) else None


def _optional_number(fields: Fields, key: str) -> float | None:
    return fields.number(key) if fields.has(key) else None


def _optional_numbers(fields: Fields, key: str) -> tuple[float, ...] | None:
    if not fields.has(key):
        return None
    found = []
    for item in fields.items(key):
        if isinstance(item, bool) or not isinstance(item, int | float):
            raise TypeError(f"{fields.where}.{key} is not a number list")
        found.append(float(item))
    return tuple(found)


def _role(value: str) -> ClassRole:
    if value not in CLASS_ROLES:
        raise TypeError(f"role {value} is outside the scenario-pack contract")
    return cast(ClassRole, value)


def _kind(value: str) -> EnvelopeKind:
    if value not in ENVELOPE_KINDS:
        raise TypeError(f"envelope kind {value} is outside the scenario-pack contract")
    return cast(EnvelopeKind, value)
