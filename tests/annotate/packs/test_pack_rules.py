"""Rules the schema cannot state: parents, bins, extents and Phase 2 class lists."""

from pathlib import Path
from typing import Any

from ss_track.annotate.packs.load import load_scenario_pack
from tests.annotate.support import changed, envelope, refused


def test_a_filled_pack_keeps_its_approval_and_phase2_slots(tmp_path: Path) -> None:
    pack = load_scenario_pack(changed(tmp_path, _fill))

    assert pack.min_box_extent_px == 8
    assert pack.min_point_extent_px == 2
    assert tuple(item.bin_id for item in pack.extent_bins) == ("small", "rest")
    assert pack.envelopes[0].approval.reference == "rec-1"
    assert pack.envelopes[0].kind == "living"
    assert pack.access_policy is not None
    assert pack.phase2 is not None
    assert pack.phase2.target_set == ("bird-of-prey",)
    assert pack.phase2.unknown_set is True
    assert pack.classes[1].min_identifiable_extent_px == 16


def test_a_parent_cycle_and_an_unknown_parent_are_refused(tmp_path: Path) -> None:
    def cycle(body: dict[str, Any]) -> None:
        body["classes"][0]["parent_class_id"] = "bird-of-prey"

    def missing(body: dict[str, Any]) -> None:
        body["classes"][0]["parent_class_id"] = "mammal"

    refused(changed(tmp_path, cycle), "bird has a parent cycle")
    refused(changed(tmp_path, missing), "unknown parent mammal")


def test_a_gap_and_an_inverted_extent_are_refused(tmp_path: Path) -> None:
    def gap(body: dict[str, Any]) -> None:
        body["limits"]["extent_bins"] = [
            {"bin_id": "small", "min_px": 0, "max_px": 8},
            {"bin_id": "rest", "min_px": 16, "max_px": None},
        ]

    def inverted(body: dict[str, Any]) -> None:
        body["limits"]["min_box_extent_px"] = 4
        body["limits"]["min_point_extent_px"] = 8

    refused(changed(tmp_path, gap), "leave a gap before rest")
    refused(changed(tmp_path, inverted), "minimum point extent exceeds minimum box extent")


def test_phase2_lists_must_name_known_disjoint_classes(tmp_path: Path) -> None:
    def shared(body: dict[str, Any]) -> None:
        body["phase2"] = {"target_set": ["bird"], "known_non_targets": ["bird"]}

    def unknown(body: dict[str, Any]) -> None:
        body["phase2"] = {"target_set": ["owl"]}

    def decreasing(body: dict[str, Any]) -> None:
        body["phase2"] = {"stand_off_levels_m": [80, 40]}

    refused(changed(tmp_path, shared), "both a target and a known non-target")
    refused(changed(tmp_path, unknown), "unknown class id owl")
    refused(changed(tmp_path, decreasing), "stand-off levels must increase")


def test_an_envelope_below_its_alert_distance_is_refused(tmp_path: Path) -> None:
    def close(body: dict[str, Any]) -> None:
        stated = envelope(approved=True)
        stated["d_alert_m"] = 10
        body["non_disturbance_envelopes"] = [stated]

    def coordinates(body: dict[str, Any]) -> None:
        stated = envelope(approved=True)
        stated["exclusion_zones"] = [
            {"zone_id": "nest-a", "radius_m": 30, "height_m": 10, "latitude": 1}
        ]
        body["non_disturbance_envelopes"] = [stated]

    refused(changed(tmp_path, close), "d_alert_m is below d_min_m")
    refused(changed(tmp_path, coordinates), "latitude")


def test_an_absent_unknown_set_stays_unset(tmp_path: Path) -> None:
    def targets_only(body: dict[str, Any]) -> None:
        body["phase2"] = {"target_set": ["bird"]}

    pack = load_scenario_pack(changed(tmp_path, targets_only))

    assert pack.phase2 is not None
    assert pack.phase2.unknown_set is None
    assert pack.phase2.declaration_deadline_s is None


def test_extent_bins_must_partition_from_zero(tmp_path: Path) -> None:
    def shifted(body: dict[str, Any]) -> None:
        body["limits"]["extent_bins"] = [{"bin_id": "rest", "min_px": 4, "max_px": None}]

    def empty(body: dict[str, Any]) -> None:
        body["limits"]["extent_bins"] = [{"bin_id": "small", "min_px": 8, "max_px": 8}]

    def bounded(body: dict[str, Any]) -> None:
        body["limits"]["extent_bins"] = [{"bin_id": "only", "min_px": 0, "max_px": 8}]

    refused(changed(tmp_path, shifted), "extent bins must start at 0 px")
    refused(changed(tmp_path, empty), "bin small is empty")
    refused(changed(tmp_path, bounded), "the last extent bin has an upper bound")


def test_repeated_activity_and_envelope_classes_are_refused(tmp_path: Path) -> None:
    def activity(body: dict[str, Any]) -> None:
        body["vocabulary"]["activity"] = ["hover", "hover"]

    def unknown(body: dict[str, Any]) -> None:
        stated = envelope(approved=True)
        stated["class_ids"] = ["owl"]
        body["non_disturbance_envelopes"] = [stated]

    def shared(body: dict[str, Any]) -> None:
        first = envelope(approved=True)
        second = envelope(approved=True)
        first["class_ids"] = ["bird"]
        second["class_ids"] = ["bird"]
        second["approval"] = {"owner": "ada", "reference": "rec-2"}
        body["non_disturbance_envelopes"] = [first, second]

    refused(changed(tmp_path, activity), "duplicate activity hover")
    refused(changed(tmp_path, unknown), "unknown class id owl")
    refused(changed(tmp_path, shared), "class bird is in more than one envelope")


def test_a_blank_class_name_and_a_repeated_stratum_are_refused(tmp_path: Path) -> None:
    def blank(body: dict[str, Any]) -> None:
        body["classes"][0]["name"] = " "

    def repeated(body: dict[str, Any]) -> None:
        body["observer_platform_strata"] = ["airborne", "airborne"]

    refused(changed(tmp_path, blank), "must not be blank")
    refused(changed(tmp_path, repeated), "duplicate stratum airborne")


def _fill(body: dict[str, Any]) -> None:
    body["limits"]["min_box_extent_px"] = 8
    body["limits"]["min_point_extent_px"] = 2
    body["limits"]["extent_bins"] = [
        {"bin_id": "small", "min_px": 0, "max_px": 8},
        {"bin_id": "rest", "min_px": 8, "max_px": None},
    ]
    body["classes"][1]["min_identifiable_extent_px"] = 16
    body["access_policy"] = {"approval": {"owner": "ada", "reference": "rec-1"}}
    stated = envelope(approved=True)
    stated["class_ids"] = ["bird"]
    body["non_disturbance_envelopes"] = [stated]
    body["phase2"] = {
        "target_set": ["bird-of-prey"],
        "known_non_targets": ["aircraft"],
        "unknown_set": True,
        "identifiable_duration_s": 1,
        "declaration_deadline_s": 10,
        "declaration_burden_per_hour": 1,
        "target_size_m": 0.3,
        "stand_off_levels_m": [40, 80],
    }
