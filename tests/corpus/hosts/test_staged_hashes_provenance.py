"""Another host's staged hashes bind the contract set they were written under (spec section 17.7).

In the development stage two hosts on different commits both write `schema_version: 1`, so equal
frame bytes do not prove that they read the records alike. Each record carries the pins of its
host's install, and `corpus compare` refuses a pair whose pins are absent or differ from its own
before it writes a comparison.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.carried_pins import carried_contract_set
from ss_track.core.refusal import RefusalCode
from ss_track.corpus import compare_staged_hashes, record_staged_hashes
from ss_track.corpus.hosts.hash_comparison import HASH_COMPARISON_NAME
from ss_track.corpus.hosts.host_hashes import run_directory
from tests.corpus.conftest import WriteCorpus, WriteRecording
from tests.corpus.hosts._host_hashes import (
    CORPUS,
    RUN,
    compare_refusal,
    declare_and_stage,
    other_host,
    stage_on_other_host,
)

ALTERED = "0" * 64


@pytest.fixture
def declared(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> tuple[Path, Path]:
    return declare_and_stage(write_recording, write_corpus, data_root)


@pytest.fixture
def left(declared: tuple[Path, Path], data_root: Path) -> Path:
    return record_staged_hashes(CORPUS, RUN, data_root).record_path


def _no_comparison(data_root: Path) -> bool:
    return not (run_directory(data_root, RUN) / HASH_COMPARISON_NAME).exists()


def test_a_record_pins_the_contract_set_it_was_written_under(left: Path) -> None:
    record = json.loads(left.read_text(encoding="ascii"))

    assert record["contract_set"] == carried_contract_set()
    pinned = {row["contract"] for row in record["contract_set"]}
    assert {"record/staged-hashes", "record/frame-set", "shared/types"} <= pinned


@pytest.mark.parametrize(
    ("installed", "contract"),
    [
        ("installed_meanings", "record/staged-hashes"),
        ("installed_meanings", "record/frame-set"),
        ("installed_fingerprints", "shared/types"),
    ],
)
@pytest.mark.parametrize("side", ["left", "right"])
def test_a_host_under_another_contract_set_refuses_before_any_write(
    declared: tuple[Path, Path],
    left: Path,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installed: str,
    contract: str,
    side: str,
) -> None:
    """The other host staged the same bytes, but under an install whose pin for `contract` differs."""
    with monkeypatch.context() as patched:
        original: dict[str, str] = getattr(contract_stamp, installed)()
        patched.setattr(contract_stamp, installed, lambda: original | {contract: ALTERED})
        other = stage_on_other_host(declared, tmp_path)
    assert (
        json.loads(other.read_text())["frame_set_sha256"]
        == json.loads(left.read_text())["frame_set_sha256"]
    )
    pair = (left, other) if side == "right" else (other, left)

    refusal = compare_refusal(*pair, data_root)

    assert refusal.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert refusal.details["changed_contracts"] == [contract]
    assert refusal.details["record"] == str(other)
    assert "spec section 17.7" in str(refusal.details["remedy"])
    assert _no_comparison(data_root)


@pytest.mark.parametrize("absent", [True, False], ids=["absent", "null"])
def test_a_record_that_states_no_contract_set_refuses(
    left: Path, data_root: Path, tmp_path: Path, absent: bool
) -> None:
    def drop(record: dict[str, Any]) -> None:
        if absent:
            record.pop("contract_set")
        else:
            record["contract_set"] = None

    unpinned = other_host(left, tmp_path, drop)

    refusal = compare_refusal(left, unpinned, data_root)

    assert refusal.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert refusal.details["field"] == "contract_set"
    assert _no_comparison(data_root)


def test_damaged_pins_are_tampered(left: Path, data_root: Path, tmp_path: Path) -> None:
    unsorted = other_host(left, tmp_path, lambda record: record["contract_set"].reverse())

    assert compare_refusal(left, unsorted, data_root).code is RefusalCode.RECORD_TAMPERED
    assert _no_comparison(data_root)


def test_released_records_carry_no_pins_and_compare_by_major(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(contract_stamp, "installed_fingerprints", lambda: None)
    monkeypatch.setattr(contract_stamp, "installed_meanings", lambda: None)
    declared = declare_and_stage(write_recording, write_corpus, data_root)
    left = record_staged_hashes(CORPUS, RUN, data_root).record_path
    right = stage_on_other_host(declared, tmp_path)

    assert json.loads(left.read_text())["contract_set"] is None
    assert compare_staged_hashes(left, right, RUN, data_root).comparison["status"] == "identical"
