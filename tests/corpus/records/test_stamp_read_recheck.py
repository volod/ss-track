"""A read whose root had no stamp when checked judges the stamp it finds after loading (17.7).

A command checks the root before it reads, and another command's first sealed write can stamp the
root and write a record between that check and the load. The loaded record is then judged by the
stamp the root now holds, as a record of a contract the stamp lacked is: served when the stamp pins
its contract as this install does, refused with `changed_contracts` when it pins it otherwise, and
refused as unstamped evidence only while the root still has no stamp.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.core.evidence import sealed
from ss_track.core.evidence.contract_stamp import (
    installed_fingerprints,
    installed_meanings,
    require_current_data_root,
)
from ss_track.core.evidence.format import RecordFormat
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.stamp_file import STAMP_NAME, write_stamp
from ss_track.core.evidence.stamp_reads import ReadGuard
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import FRAME_SET
from tests.corpus.records._unstamped import place_record

CONTRACT = "record/frame-set"
ALTERED = "0" * 64


def _first_write_between_check_and_load(
    monkeypatch: pytest.MonkeyPatch, root: Path, record: Path, pin: str | None
) -> None:
    """Let another command stamp `root` (or not, when `pin` is None) and write `record` mid-read."""
    real: Callable[[Path, str], ReadGuard | None] = sealed.check_before_read

    def racing(path: Path, kind: str) -> ReadGuard | None:
        guard = real(path, kind)
        if pin is not None:
            structures, meanings = installed_fingerprints(), installed_meanings()
            assert structures is not None and meanings is not None
            write_stamp(root / STAMP_NAME, structures | {CONTRACT: pin}, meanings)
        place_record(record)
        return guard

    monkeypatch.setattr(sealed, "check_before_read", racing)


def _read(record: Path, record_format: RecordFormat = FRAME_SET) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(record, record_format)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    return caught.value


def test_a_record_written_after_the_first_stamp_is_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    require_current_data_root(root)  # fresh: no stamp yet
    record = root / "corpus" / "pilot" / "frame-set.json"
    structures = installed_fingerprints()
    assert structures is not None
    _first_write_between_check_and_load(monkeypatch, root, record, structures[CONTRACT])

    assert read_sealed(record, FRAME_SET)["kind"] == FRAME_SET.kind


def test_a_first_stamp_of_another_install_refuses_with_its_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    require_current_data_root(root)
    record = root / "corpus" / "pilot" / "frame-set.json"
    _first_write_between_check_and_load(monkeypatch, root, record, ALTERED)

    assert _read(record).details["changed_contracts"] == [CONTRACT]


def test_a_root_still_unstamped_refuses_the_record_as_unstamped_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    require_current_data_root(root)
    record = root / "corpus" / "pilot" / "frame-set.json"
    _first_write_between_check_and_load(monkeypatch, root, record, None)

    refusal = _read(record)

    assert refusal.details["record"] == str(record)
    assert refusal.details["stamp"] == str(root / STAMP_NAME)
    assert "changed_contracts" not in refusal.details
