"""The selected workload is pinned and never silently replaces local evidence."""

import hashlib
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from ss_track.corpus.sources import pilot_workload


def test_prepare_is_repeatable_and_keeps_modified_declarations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = b"representative source bytes"
    monkeypatch.setattr(pilot_workload, "SOURCE_SHA256", hashlib.sha256(media).hexdigest())
    monkeypatch.setattr(pilot_workload, "_download", lambda path: path.write_bytes(media))

    def make_sheet(args: list[str], *, check: bool) -> CompletedProcess[str]:
        assert check
        Path(args[-1]).write_bytes(b"contact sheet")
        return CompletedProcess(args, 0)

    monkeypatch.setattr(pilot_workload.subprocess, "run", make_sheet)
    template_dir = tmp_path / "project" / pilot_workload.TEMPLATE_PATH
    template_dir.mkdir(parents=True)
    for name in ("recording.yaml", "corpus.yaml"):
        (template_dir / name).write_text(name)
    root = tmp_path / "data"
    directory = pilot_workload.prepare(root, tmp_path / "project")
    assert (directory / pilot_workload.SOURCE_NAME).read_bytes() == media
    assert (directory / "contact-sheet.jpg").read_bytes() == b"contact sheet"
    assert pilot_workload.prepare(root, tmp_path / "project") == directory

    (directory / "corpus.yaml").write_text("operator changes")
    with pytest.raises(ValueError, match="Declaration differs"):
        pilot_workload.prepare(root, tmp_path / "project")
    assert (directory / "corpus.yaml").read_text() == "operator changes"


def test_prepare_refuses_bad_download_without_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pilot_workload, "_download", lambda path: path.write_bytes(b"wrong"))
    with pytest.raises(ValueError, match="Downloaded source hash mismatch"):
        pilot_workload.prepare(tmp_path / "data", tmp_path)
    directory = tmp_path / "data" / pilot_workload.WORKLOAD_PATH
    assert list(directory.iterdir()) == []


def test_prepare_refuses_changed_existing_source(tmp_path: Path) -> None:
    directory = tmp_path / "data" / pilot_workload.WORKLOAD_PATH
    directory.mkdir(parents=True)
    source = directory / pilot_workload.SOURCE_NAME
    source.write_bytes(b"operator data")
    with pytest.raises(ValueError, match="Source hash mismatch"):
        pilot_workload.prepare(tmp_path / "data", tmp_path)
    assert source.read_bytes() == b"operator data"


def test_failed_contact_sheet_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_sheet(args: list[str], *, check: bool) -> CompletedProcess[str]:
        assert check
        Path(args[-1]).write_bytes(b"partial")
        raise OSError("ffmpeg failed")

    monkeypatch.setattr(pilot_workload.subprocess, "run", fail_sheet)
    sheet = tmp_path / "contact-sheet.jpg"
    with pytest.raises(OSError, match="ffmpeg failed"):
        pilot_workload._ensure_sheet(tmp_path / "source.webm", sheet)
    assert list(tmp_path.iterdir()) == []
