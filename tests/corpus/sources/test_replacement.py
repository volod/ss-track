"""A successor of a record read through a view keeps the record as written, under its seal."""

from pathlib import Path

import pytest

from ss_track.core.evidence.sealed import StatedRecord, read_sealed, read_stated
from ss_track.core.refusal import JsonValue
from ss_track.corpus import ImportResult, amend_source_terms
from ss_track.corpus.records.kinds import SOURCE_MANIFEST
from ss_track.corpus.sources import replacement
from ss_track.schema.registry.contract import VIEW
from tests.corpus.conftest import WriteRecording


def _read_as_a_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """Have the successor writer meet today's record as a view major that derives one value."""

    def stated(path: Path, record_format: object) -> StatedRecord:
        return StatedRecord(read_stated(path, SOURCE_MANIFEST).record, VIEW)

    def viewed(path: Path, record_format: object) -> dict[str, JsonValue]:
        record = read_sealed(path, SOURCE_MANIFEST)
        source = record["source"]
        assert isinstance(source, dict)
        return record | {"source": source | {"sha256_declared": not source["sha256_declared"]}}

    monkeypatch.setattr(replacement, "read_stated", stated)
    monkeypatch.setattr(replacement, "read_sealed", viewed)


def test_the_replaced_record_is_the_one_written_and_the_successor_carries_the_view(
    imported: ImportResult,
    write_recording: WriteRecording,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written = imported.manifest_path.read_bytes()
    _read_as_a_view(monkeypatch)

    result = amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    assert result.replaced_path is not None
    assert result.replaced_path.read_bytes() == written
    kept = read_sealed(result.replaced_path, SOURCE_MANIFEST)
    assert kept["manifest_sha256"] == imported.manifest_sha256
    successor = read_sealed(result.manifest_path, SOURCE_MANIFEST)
    assert successor["source"]["sha256_declared"] is True  # type: ignore[index, call-overload]
