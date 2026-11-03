"""Historic majors without frozen schemas remain explicit and unambiguous."""

from pathlib import Path

import pytest

from ss_track.schema import list_contracts
from ss_track.schema.check import check_contract_set
from tests.schema.conftest import read_registry, write_registry


def test_listing_exposes_retired_majors_and_their_reason() -> None:
    entries = list_contracts().to_record()["contracts"]
    assert isinstance(entries, list)
    corpus = next(
        item
        for item in entries
        if isinstance(item, dict) and item["contract"] == "record/corpus-manifest"
    )
    assert isinstance(corpus, dict)
    retired = corpus["retired_majors"]
    assert isinstance(retired, list)
    assert [item["major"] for item in retired if isinstance(item, dict)] == [1, 2]
    assert all(
        isinstance(item, dict)
        and item["status"] == "retired"
        and item["reason"]
        and item["migration"]
        for item in retired
    )


@pytest.mark.parametrize("majors", [[2, 1], [1, 1], [3]])
def test_retired_majors_cannot_repeat_or_overlap_a_frozen_version(
    contract_root: Path, majors: list[int]
) -> None:
    registry = read_registry(contract_root)
    entry = next(item for item in registry["contracts"] if item["id"] == "corpus-manifest")
    entry["retired_majors"] = [
        {
            "major": major,
            "status": "retired",
            "reason": "No runtime evidence.",
            "migration": "Write it again.",
        }
        for major in majors
    ]
    write_registry(contract_root, registry)
    assert any("retired major" in finding for finding in check_contract_set(contract_root))


@pytest.mark.parametrize("field", ["reason", "migration"])
def test_retirement_requires_a_reason_and_a_migration(contract_root: Path, field: str) -> None:
    registry = read_registry(contract_root)
    entry = next(item for item in registry["contracts"] if item["id"] == "corpus-manifest")
    del entry["retired_majors"][0][field]
    write_registry(contract_root, registry)
    assert field in check_contract_set(contract_root)[0]
