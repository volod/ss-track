"""Source inspection preserves the written capture and never reads media."""

import json
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from tests.corpus._historic import RECORDS, place_record
from tests.corpus.conftest import last_record, reseal


@pytest.mark.parametrize(
    "name",
    [
        "source-schema-1-0238d55.json",
        "source-schema-1-d6b704d.json",
        "source-schema-2-129a350.json",
    ],
)
def test_kept_records_are_inspected_without_media(
    name: str, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    original = json.loads((RECORDS / name).read_bytes())
    source = original["source"]["sha256"]
    path = place_record(name, cli_root / "import" / source / "manifest.json")
    before = path.read_bytes()
    assert main(["corpus", "inspect-source", "--source-sha256", source]) == EXIT_OK
    result = last_record(caplog)
    assert result["manifest_sha256"] == original["manifest_sha256"]
    inspection = result["source_inspection"]
    assert isinstance(inspection, dict)
    assert inspection == {
        "major": original["schema_version"],
        "disposition": "facts",
        "capture": original["capture"],
        "platform": "unknown",
    }
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("value", ["operator description", 42.5, None])
def test_retained_record_preserves_control_value(
    value: object, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    original = json.loads((RECORDS / "source-schema-1-d6b704d.json").read_bytes())
    source = original["source"]["sha256"]
    path = place_record(
        "source-schema-1-d6b704d.json", cli_root / "import" / source / "manifest.json"
    )
    capture = original["capture"] | {"camera_control_mode": value}
    reseal(path, capture=capture)
    seal = json.loads(path.read_bytes())["manifest_sha256"]
    retained = path.parent / "replaced" / f"{seal}.json"
    retained.parent.mkdir()
    retained.write_bytes(path.read_bytes())
    place_record("source-schema-1-0238d55.json", path)
    before = {p: p.read_bytes() for p in (path, retained)}
    assert (
        main(["corpus", "inspect-source", "--source-sha256", source, "--manifest-sha256", seal])
        == EXIT_OK
    )
    result = last_record(caplog)["source_inspection"]
    assert isinstance(result, dict) and result["capture"] == capture
    assert all(p.read_bytes() == content for p, content in before.items())


def test_inspection_refuses_bad_identifiers_missing_and_damaged_records(
    cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = "a" * 64

    def run(*args: str) -> str:
        assert main(["corpus", "inspect-source", *args]) == EXIT_REFUSED
        return str(last_record(caplog)["code"])

    assert run("--source-sha256", "../bad") == "MANIFEST_INVALID"
    assert run("--source-sha256", source, "--manifest-sha256", "../bad") == "MANIFEST_INVALID"
    assert run("--source-sha256", source) == "SOURCE_NOT_IMPORTED"
    path = place_record(
        "source-schema-1-d6b704d.json", cli_root / "import" / source / "manifest.json"
    )
    assert run("--source-sha256", source, "--manifest-sha256", "b" * 64) == "SOURCE_RECORD_CHANGED"
    reseal(path, kind="wrong")
    assert run("--source-sha256", source) == "RECORD_TAMPERED"
    path.write_bytes(path.read_bytes().replace(b"wrong", b"other"))
    assert run("--source-sha256", source) == "RECORD_TAMPERED"


def test_retained_record_must_match_its_requested_seal(
    cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    original = json.loads((RECORDS / "source-schema-1-d6b704d.json").read_bytes())
    source = original["source"]["sha256"]
    requested = "b" * 64
    retained = place_record(
        "source-schema-1-d6b704d.json",
        cli_root / "import" / source / "replaced" / f"{requested}.json",
    )
    args = ["corpus", "inspect-source", "--source-sha256", source, "--manifest-sha256", requested]
    assert main(args) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "SOURCE_RECORD_CHANGED"
    retained.write_bytes(retained.read_bytes().replace(b"unknown", b"tampered", 1))
    assert main(args) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "RECORD_TAMPERED"
