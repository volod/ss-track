"""A data root holds the development contract set its records were written under (spec 17.7)."""

import json
import re
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.contract_stamp import installed_fingerprints, require_current_data_root
from ss_track.core.evidence.stamp_file import (
    REGENERATE_REMEDY,
    STAMP_KIND,
    STAMP_NAME,
    read_stamp,
    write_stamp,
)
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources.importer import ImportResult
from ss_track.schema.registry.contract import STAMPED_FAMILIES
from ss_track.schema.validation.enforce import SHARED_TYPES, installed_contracts
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


def test_first_write_stamps_every_record_contract_and_a_read_preserves_it(
    imported: ImportResult,
    write_recording: WriteRecording,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    original = (cli_root / STAMP_NAME).read_bytes()
    assert main([*_INSPECT, imported.source_sha256]) == EXIT_OK
    assert (cli_root / STAMP_NAME).read_bytes() == original

    assert main(_amend(write_recording)) == EXIT_OK

    stamp = json.loads((cli_root / STAMP_NAME).read_text(encoding="ascii"))
    assert stamp["contracts"] == installed_fingerprints()
    assert "record/source-manifest" in stamp["contracts"]
    assert "result/command" not in stamp["contracts"]


def test_read_only_command_on_fresh_root_writes_no_stamp(cli_root: Path) -> None:
    assert main([*_INSPECT, "0" * 64]) == EXIT_REFUSED
    assert not (cli_root / STAMP_NAME).exists()


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
        json.dumps({"kind": STAMP_KIND, "contracts": installed_fingerprints()})
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
    (tmp_path / STAMP_NAME).write_text(text.replace("%s", STAMP_KIND))

    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(tmp_path)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b'{"kind":"ss-track.development-contract-set","contracts":{},"contracts":{}}',
        b'{"kind":"ss-track.development-contract-set","contracts":{"record/frame-set":42}}',
    ],
)
def test_malformed_stamp_is_tampered(tmp_path: Path, payload: bytes) -> None:
    (tmp_path / STAMP_NAME).write_bytes(payload)
    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(tmp_path)
    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_stamp_precedes_sealed_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ss_track.core.evidence import sealing
    from tests.schema.conftest import KEPT_FRAME_SET

    require_current_data_root(tmp_path)
    target = tmp_path / "records" / "record.json"

    def fail_record_write(path: Path, payload: bytes, *, mode: int) -> None:
        assert (tmp_path / STAMP_NAME).is_file()
        raise OSError("interrupted record write")

    monkeypatch.setattr(sealing, "write_atomically", fail_record_write)
    with pytest.raises(OSError, match="interrupted record write"):
        sealing.write_sealed(target, json.loads(KEPT_FRAME_SET.read_bytes()))
    assert not target.exists()


def test_first_write_rechecks_stamp_created_by_another_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    require_current_data_root(tmp_path)
    current = installed_fingerprints()
    assert current is not None
    old = current | {"record/frame-set": "0" * 64}
    (tmp_path / STAMP_NAME).write_text(json.dumps({"kind": STAMP_KIND, "contracts": old}))
    with pytest.raises(CorpusRefusal) as caught:
        contract_stamp.stamp_before_write(tmp_path / "record.json")
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert json.loads((tmp_path / STAMP_NAME).read_text())["contracts"] == old


def test_meaning_only_edit_refuses_the_old_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    require_current_data_root(tmp_path)
    contract_stamp.stamp_before_write(tmp_path / "record.json")
    original = contract_stamp.installed_meanings()
    assert original is not None
    monkeypatch.setattr(
        contract_stamp, "installed_meanings", lambda: original | {"record/frame-set": "0" * 64}
    )
    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(tmp_path)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert caught.value.details["changed_contracts"] == ["record/frame-set"]


def test_shared_contract_edit_refuses_the_old_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    require_current_data_root(tmp_path)
    contract_stamp.stamp_before_write(tmp_path / "record.json")
    original = installed_fingerprints()
    assert original is not None and "shared/types" in original
    monkeypatch.setattr(
        contract_stamp, "installed_fingerprints", lambda: original | {"shared/types": "0" * 64}
    )
    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(tmp_path)
    assert caught.value.details["changed_contracts"] == ["shared/types"]


def test_legacy_structure_only_stamp_refuses_without_deleting_data(tmp_path: Path) -> None:
    original = installed_fingerprints()
    assert original is not None
    (tmp_path / STAMP_NAME).write_text(
        json.dumps(
            {
                "kind": STAMP_KIND,
                "contracts": {
                    name: value for name, value in original.items() if name.startswith("record/")
                },
            }
        )
    )
    evidence = tmp_path / "record.json"
    evidence.write_text("retained evidence")
    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(tmp_path)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert caught.value.details["changed_contracts"] == []
    assert "record/frame-set" in caught.value.details["unverified_contracts"]
    assert evidence.read_text() == "retained evidence"


def test_the_stamp_and_carried_pins_admit_exactly_the_stamped_families(tmp_path: Path) -> None:
    """`STAMPED_FAMILIES` names what the stamp pins; its parser and the carried rows follow it."""
    contracts = installed_contracts().contracts
    types = contracts.named(SHARED_TYPES)
    rows = contracts.frozen_schema(types, types.versions[-1])["$defs"]["contract-set"]
    pattern = str(rows["items"]["properties"]["contract"]["pattern"])
    for family in sorted({contract.family for contract in contracts.contracts}):
        name = f"{family}/probe"
        write_stamp(tmp_path / STAMP_NAME, {name: "a" * 64}, {name: "a" * 64})
        try:
            parsed = read_stamp(tmp_path / STAMP_NAME) is not None
        except CorpusRefusal:
            parsed = False
        stamped = family in STAMPED_FAMILIES
        assert (parsed, re.fullmatch(pattern, name) is not None) == (stamped, stamped), family
