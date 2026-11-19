"""Historic majors without frozen schemas: released only, explicit and unambiguous."""

from pathlib import Path
from typing import Any

import pytest

from ss_track.schema import list_contracts
from ss_track.schema.registry.check import check_contract_set
from tests.schema.conftest import read_registry, write_registry


def _retire(root: Path, majors: list[int]) -> dict[str, Any]:
    """Give the corpus manifest historic majors with no frozen contract, and return its entry."""
    registry = read_registry(root)
    entry: dict[str, Any] = next(
        item for item in registry["contracts"] if item["id"] == "corpus-manifest"
    )
    entry["retired_majors"] = [
        {
            "major": major,
            "status": "retired",
            "reason": "No runtime evidence.",
            "migration": "Write it again.",
        }
        for major in majors
    ]
    write_registry(root, registry)
    return entry


def test_listing_exposes_retired_majors_and_their_reason(contract_root: Path) -> None:
    _retire(contract_root, [2, 3])
    assert check_contract_set(contract_root) == []

    entries = list_contracts(contract_root).to_record()["contracts"]

    assert isinstance(entries, list)
    corpus = next(
        item
        for item in entries
        if isinstance(item, dict) and item["contract"] == "record/corpus-manifest"
    )
    assert isinstance(corpus, dict)
    retired = corpus["retired_majors"]
    assert isinstance(retired, list)
    assert [item["major"] for item in retired if isinstance(item, dict)] == [2, 3]
    assert all(
        isinstance(item, dict)
        and item["status"] == "retired"
        and item["reason"]
        and item["migration"]
        for item in retired
    )


def test_the_development_stage_holds_no_retired_major(development_root: Path) -> None:
    _retire(development_root, [2])

    assert check_contract_set(development_root) == [
        "record/corpus-manifest: the development stage holds no retired major"
    ]


@pytest.mark.parametrize("majors", [[3, 2], [2, 2], [1]])
def test_retired_majors_cannot_repeat_or_overlap_a_frozen_version(
    contract_root: Path, majors: list[int]
) -> None:
    _retire(contract_root, majors)
    assert any("retired major" in finding for finding in check_contract_set(contract_root))


@pytest.mark.parametrize("field", ["reason", "migration"])
def test_retirement_requires_a_reason_and_a_migration(contract_root: Path, field: str) -> None:
    entry = _retire(contract_root, [2])
    registry = read_registry(contract_root)
    found = next(item for item in registry["contracts"] if item["id"] == entry["id"])
    del found["retired_majors"][0][field]
    write_registry(contract_root, registry)
    assert field in check_contract_set(contract_root)[0]
