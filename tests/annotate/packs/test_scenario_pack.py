"""The draft pack validates, and the hash moves when a pinned value moves."""

from pathlib import Path
from typing import Any

import yaml

from ss_track.annotate.packs.load import load_scenario_pack
from ss_track.annotate.packs.model import CLASS_ROLES
from ss_track.annotate.packs.rules import RULES
from ss_track.schema import validate_file
from ss_track.schema.registry.store import load_contract_set
from tests.annotate.support import (
    DRAFT,
    EXAMPLE,
    changed,
    document,
    envelope,
    refused,
    write_pack,
)

_MISSION = ("bird", "bird-of-prey", "drone", "aircraft", "insect", "clutter")


def test_contracts_validate_accepts_the_draft() -> None:
    result = validate_file(DRAFT, contract_name="declaration/scenario-pack")

    assert result.to_record()["status"] == "valid"
    assert result.to_record()["contract"] == "declaration/scenario-pack"
    assert result.to_record()["version"] == "1.0.0"


def test_the_draft_names_the_mission_classes_and_leaves_owner_values_unset() -> None:
    pack = load_scenario_pack(DRAFT)

    assert tuple(item.class_id for item in pack.classes) == _MISSION
    assert tuple(item.role for item in pack.classes) == (
        "scoring",
        "scoring",
        "scoring",
        "scoring",
        "distractor",
        "ignore",
    )
    assert tuple(item.parent_class_id for item in pack.classes) == (
        None,
        "bird",
        None,
        None,
        None,
        None,
    )
    assert tuple(item.name for item in pack.classes) == (
        "bird",
        "bird of prey",
        "drone",
        "aircraft",
        "insect",
        "clutter",
    )
    assert pack.min_box_extent_px is None
    assert pack.min_point_extent_px is None
    assert pack.extent_bins == ()
    assert pack.envelopes == ()
    assert pack.phase2 is None
    assert pack.access_policy is None
    assert pack.vocabulary.activity == ()
    assert all(item.min_identifiable_extent_px is None for item in pack.classes)
    assert pack.pack_hash == load_scenario_pack(EXAMPLE).pack_hash


def test_class_role_extent_and_bin_each_change_the_pack_hash(tmp_path: Path) -> None:
    original = load_scenario_pack(DRAFT).pack_hash
    edits = (_rename_class, _change_role, _set_extent, _set_bins)
    hashes = {load_scenario_pack(changed(tmp_path, edit)).pack_hash for edit in edits}

    assert original not in hashes
    assert len(hashes) == len(edits)


def test_object_key_order_does_not_change_the_pack_hash(tmp_path: Path) -> None:
    body = document()
    ordered = write_pack(tmp_path, body)
    sorted_path = tmp_path / "sorted.yaml"
    sorted_path.write_text(yaml.safe_dump(body, sort_keys=True), encoding="utf-8")

    assert load_scenario_pack(ordered).pack_hash == load_scenario_pack(sorted_path).pack_hash


def test_a_duplicate_class_id_is_refused(tmp_path: Path) -> None:
    def duplicate(body: dict[str, Any]) -> None:
        body["classes"][5]["class_id"] = "bird"

    refused(changed(tmp_path, duplicate), "duplicate class id bird")


def test_a_class_with_no_role_is_refused(tmp_path: Path) -> None:
    def drop_role(body: dict[str, Any]) -> None:
        del body["classes"][0]["role"]

    refused(changed(tmp_path, drop_role), "role")


def test_an_overlapping_extent_bin_is_refused(tmp_path: Path) -> None:
    def overlap(body: dict[str, Any]) -> None:
        body["limits"]["extent_bins"] = [
            {"bin_id": "small", "min_px": 0, "max_px": 10},
            {"bin_id": "medium", "min_px": 8, "max_px": None},
        ]

    refused(changed(tmp_path, overlap), "bin small overlaps medium")


def test_an_envelope_without_an_approval_record_is_refused(tmp_path: Path) -> None:
    def fill(body: dict[str, Any]) -> None:
        body["non_disturbance_envelopes"] = [envelope(approved=False)]

    refusal = refused(changed(tmp_path, fill), "approval")
    assert refusal.code.value == "MANIFEST_INVALID"


def test_an_extent_envelope_floor_on_the_pack_is_refused(tmp_path: Path) -> None:
    # Spec section 6.7: the scenario declares the floor per measure. A pack-level floor
    # would tie a quality threshold to the hash that frozen labels pin.
    def under_limits(body: dict[str, Any]) -> None:
        body["limits"]["extent_floor"] = 0.5

    def at_top(body: dict[str, Any]) -> None:
        body["extent_floors"] = {"success": 0.5}

    refused(changed(tmp_path, under_limits), "extent_floor")
    refused(changed(tmp_path, at_top), "extent_floors")


def test_loader_rules_and_roles_match_the_contract() -> None:
    contracts = load_contract_set()
    contract = contracts.named("declaration/scenario-pack")
    newest = contract.newest()
    assert newest is not None
    schema = contracts.frozen_schema(contract, newest)
    recording = contracts.named("declaration/recording")
    recording_version = recording.newest()
    assert recording_version is not None
    platforms = contracts.frozen_schema(recording, recording_version)
    strata = platforms["properties"]["capture"]["properties"]["observer_platform"]["enum"]

    assert set(schema["x-rules"]) == set(RULES)
    assert tuple(schema["$defs"]["class-entry"]["properties"]["role"]["enum"]) == CLASS_ROLES
    assert schema["properties"]["observer_platform_strata"]["items"]["enum"] == strata


def _rename_class(body: dict[str, Any]) -> None:
    body["classes"][0]["name"] = "birds"


def _change_role(body: dict[str, Any]) -> None:
    body["classes"][5]["role"] = "distractor"


def _set_extent(body: dict[str, Any]) -> None:
    body["limits"]["min_box_extent_px"] = 8


def _set_bins(body: dict[str, Any]) -> None:
    body["limits"]["extent_bins"] = [
        {"bin_id": "small", "min_px": 0, "max_px": 8},
        {"bin_id": "rest", "min_px": 8, "max_px": None},
    ]
