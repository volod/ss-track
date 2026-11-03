"""Closed previous contracts and retained producer output guard unchanged-feature writes."""

import copy
import json
from typing import Any

import pytest
from referencing import Registry

from ss_track.canonical import canonical_json
from ss_track.corpus.frame_set import _seal_found
from ss_track.schema.store import load_contract_set
from ss_track.schema.strict import violations
from tests._sealing import self_sealed
from tests.corpus._historic import kept_record
from tests.schema.conftest import KEPT_FRAME_SET
from tests.schema.test_evolution import obj


def require_stable_output(
    previous: dict[str, Any],
    output: dict[str, Any],
    schema: dict[str, Any],
    registry: Registry[Any],
) -> None:
    assert not violations(output, schema, registry), (
        "writer no longer validates against previous minor"
    )
    assert canonical_json(previous) == canonical_json(output), (
        "writer changed existing bytes or seal"
    )


def test_real_writer_replays_kept_input_under_every_previous_minor() -> None:
    corpus = json.loads(kept_record("corpus-schema-3-129a350.json"))
    previous = json.loads(KEPT_FRAME_SET.read_bytes())
    hashes = {entry["stream_id"]: entry["bundle_sha256"] for entry in previous["bundles"]}
    # The retained frame set names the same corpus content under a different corpus id.
    corpus["corpus_id"] = previous["corpus_id"]
    corpus["manifest_sha256"] = previous["corpus_manifest_sha256"]
    by_id = {
        entry["stream_id"]: entry
        for entry in previous["bundles"]
        if entry["parent_stream_id"] is None
    }
    corpus["streams"] = [
        {
            "stream_id": name,
            "source_sha256": entry["source_sha256"],
            "source_manifest_sha256": entry["source_manifest_sha256"],
        }
        for name, entry in by_id.items()
    ]
    corpus["generated_cases"] = [
        {"case_id": entry["stream_id"], "parent_stream_id": entry["parent_stream_id"]}
        for entry in previous["bundles"]
        if entry["parent_stream_id"] is not None
    ]
    output = _seal_found(corpus, hashes)
    contracts = load_contract_set()
    contract = contracts.named("record/frame-set")
    for frozen in contract.versions:
        if frozen.major == output["schema_version"]:
            require_stable_output(
                previous,
                output,
                contracts.frozen_schema(contract, frozen),
                contracts.schema_registry(),
            )


@pytest.mark.parametrize("value", [None, "default"])
def test_unused_new_field_fails_even_when_latest_minor_accepts_it(value: Any) -> None:
    before = self_sealed({"kind": "test", "schema_version": 1})
    schema = obj(
        {
            "kind": {"type": "string"},
            "schema_version": {"type": "integer"},
            "manifest_sha256": {"type": "string"},
        }
    )
    latest = copy.deepcopy(schema)
    latest["properties"]["new"] = {"type": ["string", "null"]}
    after = self_sealed(before | {"new": value})
    assert not violations(after, latest, Registry())
    with pytest.raises(AssertionError, match="previous minor"):
        require_stable_output(before, after, schema, Registry())


def test_unannounced_key_and_changed_existing_value_fail() -> None:
    schema = obj({"name": {"type": "string"}})
    with pytest.raises(AssertionError, match="previous minor"):
        require_stable_output({"name": "a"}, {"name": "a", "unannounced": 1}, schema, Registry())
    with pytest.raises(AssertionError, match="existing bytes"):
        require_stable_output({"name": "a"}, {"name": "b"}, schema, Registry())


def test_existing_cli_result_validates_against_the_previous_frozen_minor() -> None:
    from ss_track.schema.commands import validate_file

    contracts = load_contract_set()
    contract = contracts.named("result/command")
    assert len(contract.versions) >= 2
    record = validate_file(KEPT_FRAME_SET).to_record()
    for frozen in contract.versions[:-1]:
        assert not violations(
            record, contracts.frozen_schema(contract, frozen), contracts.schema_registry()
        )
