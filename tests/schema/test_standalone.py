"""A consumer with only `contracts/` and a standard validator reads a record."""

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.schema.conftest import CONTRACTS, KEPT_FRAME_SET

_SCRIPT = Path(__file__).with_name("_standalone.py")


def _verdict(contracts: Path, document: Path, working: Path) -> str:
    """Run isolated, so neither this checkout nor its environment variables can help."""
    completed = subprocess.run(
        [sys.executable, "-I", str(_SCRIPT), str(contracts), str(document)],
        capture_output=True,
        text=True,
        cwd=working,
        env={},
        check=True,
    )
    return completed.stdout.strip()


@pytest.fixture
def only_contracts(tmp_path: Path) -> Path:
    copied = tmp_path / "copied" / "contracts"
    shutil.copytree(CONTRACTS, copied, ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    return copied


@pytest.mark.parametrize(
    "document", sorted(Path(__file__).with_name("examples").glob("record-*.json"))
)
def test_every_record_example_is_accepted(
    only_contracts: Path, tmp_path: Path, document: Path
) -> None:
    assert _verdict(only_contracts, document, tmp_path) == "valid"


def test_the_standard_validator_refuses_a_four_position_frame_tuple(
    only_contracts: Path, tmp_path: Path
) -> None:
    source = Path(__file__).with_name("examples") / "record-staged-hashes.json"
    record = json.loads(source.read_text())
    record["bundles"][0]["frames"][0].append("extra")
    document = tmp_path / "extra.json"
    document.write_text(json.dumps(record))
    assert _verdict(only_contracts, document, tmp_path) == "invalid"


def _add_key(record: dict[str, Any]) -> None:
    record["surprise"] = 1


def _break_hash(record: dict[str, Any]) -> None:
    record["bundles"][0]["bundle_sha256"] = "abc"


def _drop_key(record: dict[str, Any]) -> None:
    del record["corpus_id"]


def _change_kind_field(record: dict[str, Any]) -> None:
    record["bundles"][0]["surprise"] = True


@pytest.mark.parametrize("alter", [_add_key, _break_hash, _drop_key, _change_kind_field])
def test_an_altered_copy_is_refused(
    only_contracts: Path, tmp_path: Path, alter: Callable[[dict[str, Any]], None]
) -> None:
    record = json.loads(KEPT_FRAME_SET.read_text(encoding="ascii"))
    alter(record)
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(record), encoding="ascii")

    assert _verdict(only_contracts, altered, tmp_path) == "invalid"


def test_the_seal_rule_in_words_is_enough_to_recompute_a_seal() -> None:
    """A schema cannot check a seal, so `x-rules` must state it exactly: this follows its words."""
    record = json.loads(KEPT_FRAME_SET.read_text(encoding="ascii"))
    pinned = record.pop("manifest_sha256")
    text = json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    assert hashlib.sha256(text.encode("ascii")).hexdigest() == pinned


def test_the_contracts_name_only_each_other(only_contracts: Path) -> None:
    urn_prefix = "urn:ss-track:contract:"
    identities = set()
    references = set()
    for path in only_contracts.rglob("*.json"):
        text = json.loads(path.read_text(encoding="utf-8"))
        if path.relative_to(only_contracts) == Path("meta/standards/odcs-3.2.0.json"):
            assert all(reference.startswith("#") for reference in _references(text))
            continue
        identities.add(text["$id"])
        references.update(_references(text))

    remote = {item for item in references if not item.startswith(("#", urn_prefix))}
    assert remote == set()
    assert {item.partition("#")[0] for item in references if item[0] != "#"} <= identities


def _references(node: object) -> set[str]:
    if isinstance(node, dict):
        found = {node["$ref"]} if isinstance(node.get("$ref"), str) else set()
        return found.union(*map(_references, node.values()))
    if isinstance(node, list):
        return set().union(*map(_references, node))
    return set()
