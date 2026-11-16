"""Source inspection preserves the written capture and never reads media."""

import json
import shutil
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus.sources.importer import ImportResult
from tests.corpus.conftest import last_record, reseal


def test_a_current_record_is_inspected_without_media(
    imported: ImportResult, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = imported.manifest_path
    original = json.loads(path.read_bytes())
    before = path.read_bytes()

    assert main(["corpus", "inspect-source", "--source-sha256", imported.source_sha256]) == EXIT_OK

    result = last_record(caplog)
    assert result["manifest_sha256"] == imported.manifest_sha256
    assert result["source_inspection"] == {
        "major": original["schema_version"],
        "disposition": "current",
        "capture": original["capture"],
        "platform": original["capture"].get("observer_platform", "unknown"),
    }
    assert path.read_bytes() == before


@pytest.mark.parametrize("value", ["operator description", 42.5, None])
def test_retained_record_preserves_control_value(
    value: object, imported: ImportResult, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = imported.manifest_path
    current = path.read_bytes()
    path.chmod(0o644)
    capture = json.loads(current)["capture"] | {"camera_control_mode": value}
    reseal(path, capture=capture)
    seal = json.loads(path.read_bytes())["manifest_sha256"]
    retained = path.parent / "replaced" / f"{seal}.json"
    retained.parent.mkdir()
    shutil.copyfile(path, retained)
    path.write_bytes(current)
    before = {p: p.read_bytes() for p in (path, retained)}
    source = imported.source_sha256

    args = ["corpus", "inspect-source", "--source-sha256", source, "--manifest-sha256", seal]
    assert main(args) == EXIT_OK

    result = last_record(caplog)["source_inspection"]
    assert isinstance(result, dict) and result["capture"] == capture
    assert all(p.read_bytes() == content for p, content in before.items())


def test_inspection_refuses_bad_identifiers_missing_and_damaged_records(
    imported: ImportResult, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def run(*args: str) -> str:
        assert main(["corpus", "inspect-source", *args]) == EXIT_REFUSED
        return str(last_record(caplog)["code"])

    source = imported.source_sha256
    assert run("--source-sha256", "../bad") == "MANIFEST_INVALID"
    assert run("--source-sha256", source, "--manifest-sha256", "../bad") == "MANIFEST_INVALID"
    assert run("--source-sha256", "a" * 64) == "SOURCE_NOT_IMPORTED"
    assert run("--source-sha256", source, "--manifest-sha256", "b" * 64) == "SOURCE_RECORD_CHANGED"
    path = imported.manifest_path
    path.chmod(0o644)
    reseal(path, kind="wrong")
    assert run("--source-sha256", source) == "RECORD_TAMPERED"
    path.write_bytes(path.read_bytes().replace(b"wrong", b"other"))
    assert run("--source-sha256", source) == "RECORD_TAMPERED"


def test_retained_record_must_match_its_requested_seal(
    imported: ImportResult, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    requested = "b" * 64
    retained = imported.manifest_path.parent / "replaced" / f"{requested}.json"
    retained.parent.mkdir()
    shutil.copyfile(imported.manifest_path, retained)
    source = imported.source_sha256
    args = ["corpus", "inspect-source", "--source-sha256", source, "--manifest-sha256", requested]

    assert main(args) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "SOURCE_RECORD_CHANGED"
    retained.write_bytes(retained.read_bytes().replace(b"capture", b"captura", 1))
    assert main(args) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "RECORD_TAMPERED"
