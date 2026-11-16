"""A data root holds the development contract set its records were written under (spec 17.7)."""

import json
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.contract_stamp import (
    REGENERATE_REMEDY,
    STAMP_NAME,
    installed_fingerprints,
    require_current_data_root,
)
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources.importer import ImportResult
from tests.corpus._amending import rights_with
from tests.corpus.conftest import WriteRecording, last_record

_INSPECT = ["corpus", "inspect-source", "--source-sha256"]


def _edit_contract(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Install a set whose `name` contract was edited in place since the root was stamped."""
    installed = installed_fingerprints()
    assert installed is not None
    edited = installed | {name: "0" * 64}
    monkeypatch.setattr(contract_stamp, "installed_fingerprints", lambda: edited)


def _amend(write_recording: WriteRecording) -> list[str]:
    """A command that writes a sealed record: a successor source record with other terms."""
    declared = write_recording(rights=rights_with(sharing="public"))
    return ["import", "--source", str(declared), "--amend-terms"]


def test_a_read_writes_no_stamp_and_a_first_write_stamps_every_record_contract(
    imported: ImportResult,
    write_recording: WriteRecording,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert main([*_INSPECT, imported.source_sha256]) == EXIT_OK
    assert not (cli_root / STAMP_NAME).exists()

    assert main(_amend(write_recording)) == EXIT_OK

    stamp = json.loads((cli_root / STAMP_NAME).read_text(encoding="ascii"))
    assert stamp["contracts"] == installed_fingerprints()
    assert "record/source-manifest" in stamp["contracts"]
    assert "result/command" not in stamp["contracts"]


def test_a_root_written_before_an_edit_is_refused_with_the_regenerate_remedy(
    imported: ImportResult,
    write_recording: WriteRecording,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert main(_amend(write_recording)) == EXIT_OK
    stamp = (cli_root / STAMP_NAME).read_bytes()
    _edit_contract(monkeypatch, "record/source-manifest")

    assert main([*_INSPECT, imported.source_sha256]) == EXIT_REFUSED

    refusal = last_record(caplog)
    assert refusal["code"] == "RECORD_SCHEMA_UNSUPPORTED"
    details = refusal["details"]
    assert isinstance(details, dict)
    assert details["changed_contracts"] == ["record/source-manifest"]
    assert details["remedy"] == REGENERATE_REMEDY
    assert (cli_root / STAMP_NAME).read_bytes() == stamp


def test_data_clean_serves_a_stale_root(
    cli_root: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_root.mkdir(parents=True, exist_ok=True)
    (cli_root / STAMP_NAME).write_text(
        json.dumps({"kind": contract_stamp.STAMP_KIND, "contracts": installed_fingerprints()})
    )
    _edit_contract(monkeypatch, "record/frame-bundle")
    with pytest.raises(CorpusRefusal):
        require_current_data_root(cli_root)

    assert main(["data", "clean", "--kind", "scratch"]) == EXIT_OK


def test_a_released_set_writes_and_reads_no_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contract_stamp, "installed_fingerprints", lambda: None)
    (tmp_path / STAMP_NAME).write_text("not read", encoding="ascii")

    require_current_data_root(tmp_path)
    require_current_data_root(tmp_path / "fresh")

    assert not (tmp_path / "fresh" / STAMP_NAME).exists()


@pytest.mark.parametrize("text", ["{", "[]", '{"kind": "other"}', '{"kind": "%s"}'])
def test_a_damaged_stamp_is_refused(tmp_path: Path, text: str) -> None:
    (tmp_path / STAMP_NAME).write_text(text.replace("%s", contract_stamp.STAMP_KIND))

    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(tmp_path)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
