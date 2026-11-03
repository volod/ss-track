"""Where a contract and code must still say one thing twice, these keep the two from drifting."""

import json
import re
from pathlib import Path

from ss_track.corpus.frame_set import FRAME_SET
from ss_track.quality.plan_model import read_registry as read_capabilities
from ss_track.refusal import RefusalCode
from tests.schema.conftest import CONTRACTS, PROJECT_ROOT, frame_set_path, read_registry


def _types() -> dict[str, dict[str, str]]:
    path = CONTRACTS / "shared" / "types" / "1.0.0.json"
    definitions: dict[str, dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))["$defs"]
    return definitions


def test_a_nullable_identifier_repeats_the_shared_pattern() -> None:
    schema = json.loads(frame_set_path(CONTRACTS).read_text(encoding="utf-8"))
    parent = schema["$defs"]["bundle"]["properties"]["parent_stream_id"]

    assert parent["pattern"] == _types()["identifier"]["pattern"]


def test_the_frame_set_contract_stamps_what_its_writer_stamps() -> None:
    schema = json.loads(frame_set_path(CONTRACTS).read_text(encoding="utf-8"))

    assert schema["properties"]["kind"]["const"] == FRAME_SET.kind
    assert schema["properties"]["schema_version"]["const"] == FRAME_SET.major


def test_every_owner_is_a_capability_of_the_specification() -> None:
    spec = PROJECT_ROOT / "docs" / "design" / "spec.md"
    capabilities = {capability.identifier for capability in read_capabilities(spec)}
    owners = {entry["owner"] for entry in read_registry(CONTRACTS)["contracts"]}

    assert owners <= capabilities


def test_the_refusal_codes_an_operator_can_meet_are_documented() -> None:
    page = (PROJECT_ROOT / "docs" / "impl" / "current" / "contracts.md").read_text(encoding="utf-8")
    codes = (
        RefusalCode.CONTRACT_UNKNOWN,
        RefusalCode.CONTRACT_SET_INVALID,
        RefusalCode.RECORD_INVALID,
        RefusalCode.RECORD_TAMPERED,
    )

    assert all(re.search(rf"`{code.value}`", page) for code in codes)


def test_the_gate_runs_inside_ci() -> None:
    makefile = Path(PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    checks = re.search(r"^ci-checks:((?:.*\\\n)*.*)$", makefile, re.MULTILINE)

    assert checks is not None
    assert "lint-contracts" in checks.group(1)
