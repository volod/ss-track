"""Where a contract and code must still say one thing twice, these keep the two from drifting."""

import json
import re
from pathlib import Path

import pytest

from ss_track.core.refusal import RefusalCode
from ss_track.corpus.bundles.frame_set import FRAME_SET
from ss_track.corpus.bundles.frames import FRAME_BUNDLE
from ss_track.corpus.declarations.fields import TEXT_RULE
from ss_track.corpus.descriptors.descriptor_public import SPLITS
from ss_track.corpus.hosts.hash_comparison import HASH_COMPARISON
from ss_track.corpus.hosts.host_hashes import STAGED_HASHES
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.sources.importer import SOURCE_MANIFEST
from ss_track.corpus.versions.builder import CORPUS_MANIFEST
from ss_track.quality.plan_model import read_registry as read_capabilities
from ss_track.schema.registry.contract import DECLARATION_FAMILY
from ss_track.schema.registry.fingerprints import walk
from ss_track.schema.registry.store import load_contract_set
from tests.schema.conftest import CONTRACTS, PROJECT_ROOT, frame_set_path, read_registry

_WRITTEN = (
    CORPUS_MANIFEST,
    FRAME_BUNDLE,
    FRAME_SET,
    HASH_COMPARISON,
    SOURCE_MANIFEST,
    STAGED_HASHES,
)


def _types() -> dict[str, dict[str, str]]:
    path = CONTRACTS / "shared" / "types" / "1.0.0.json"
    definitions: dict[str, dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))["$defs"]
    return definitions


def test_a_nullable_identifier_repeats_the_shared_pattern() -> None:
    schema = json.loads(frame_set_path(CONTRACTS).read_text(encoding="utf-8"))
    parent = schema["$defs"]["bundle"]["properties"]["parent_stream_id"]

    assert parent["pattern"] == _types()["identifier"]["pattern"]


@pytest.mark.parametrize("record_format", _WRITTEN, ids=lambda item: item.kind)
def test_each_record_contract_stamps_what_its_writer_stamps(record_format: RecordFormat) -> None:
    contracts = load_contract_set(CONTRACTS)
    contract = contracts.records_by_kind()[record_format.kind]
    newest = contract.newest()

    assert newest is not None and newest.major == record_format.major


def test_the_descriptor_counts_every_split_the_corpus_contract_states() -> None:
    contracts = load_contract_set(CONTRACTS)
    contract = contracts.records_by_kind()[CORPUS_MANIFEST.kind]
    newest = contract.newest()
    assert newest is not None
    stream = contracts.frozen_schema(contract, newest)["properties"]["streams"]["items"]

    assert set(SPLITS) == set(stream["properties"]["split"]["enum"])


def _free_text(node: dict[str, object]) -> bool:
    """A string an operator writes freely: no vocabulary, pattern or format bounds it."""
    bounded = ("pattern", "enum", "const", "format", "$ref")
    return node.get("type") == "string" and not any(key in node for key in bounded)


def test_every_free_text_declaration_field_states_the_not_blank_rule_its_reader_applies() -> None:
    """`Fields.text` refuses whitespace-only text, which the dialect cannot state but `x-rules` can."""
    contracts = load_contract_set(CONTRACTS)
    missing = []
    for contract in contracts.contracts:
        newest = contract.newest()
        if contract.family != DECLARATION_FAMILY or newest is None:
            continue
        for node in walk(contracts.frozen_schema(contract, newest)):
            rules = node.get("x-rules", {})
            if _free_text(node) and TEXT_RULE not in rules:
                missing.append(f"{contract.urn(newest)}: {node.get('description')}")

    assert missing == []


def test_every_record_contract_has_a_writer() -> None:
    kinds = set(load_contract_set(CONTRACTS).records_by_kind())

    assert kinds == {record_format.kind for record_format in _WRITTEN}


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
