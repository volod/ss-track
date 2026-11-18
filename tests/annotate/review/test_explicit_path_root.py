"""`annotate freeze` with explicit output paths holds a data root it writes into to its contracts.

A revision published inside `DATA_DIR` is data-root evidence, so the freeze checks the root first
and the write stamps it, as every other sealed write does. A freeze outside the root is standalone.
"""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ss_track.annotate.review.revision import read_annotation_revision
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.cli import main
from ss_track.core.evidence.contract_stamp import STAMP_NAME
from ss_track.core.refusal import RefusalCode
from tests.annotate.review_files import write_pair, write_review, write_settlement
from tests.annotate.support import DRAFT

_SHA = "0" * 64


def _inputs(folder: Path, pack: object, clip: Path) -> Path:
    write_pair(folder, pack, lambda _: None, read_frame_space(clip))  # type: ignore[arg-type]
    write_review(folder)
    return write_settlement(folder, [])


def _freeze(folder: Path, clip: Path, out: Path) -> list[str]:
    return [
        "annotate",
        "freeze",
        "--left",
        str(folder / "left.yaml"),
        "--right",
        str(folder / "right.yaml"),
        "--pack",
        str(DRAFT),
        "--source",
        str(clip),
        "--review",
        str(folder / "review.yaml"),
        "--settlement",
        str(folder / "settlement.yaml"),
        "--labels-out",
        str(out / "frozen.json"),
        "--revision-out",
        str(out / "revision.json"),
    ]


def _record(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    loaded = json.loads(caplog.records[-1].getMessage())
    assert isinstance(loaded, dict)
    return loaded


def _inspect() -> list[str]:
    return ["corpus", "inspect-source", "--source-sha256", _SHA]


@pytest.mark.parametrize("nested", ["", "labels/g0"])
def test_a_freeze_into_a_fresh_root_stamps_it_for_the_next_command(
    tmp_path: Path,
    pack: object,
    rotated_clip: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    nested: str,
) -> None:
    root = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(root))
    caplog.set_level(logging.INFO)
    folder = tmp_path / "inputs"
    _inputs(folder, pack, rotated_clip)

    assert main(_freeze(folder, rotated_clip, root / nested)) == 0
    assert (root / STAMP_NAME).is_file()
    assert read_annotation_revision(root / nested / "revision.json")["kind"]
    # The root check passes, so the command reaches its own answer for an unknown source.
    assert main(_inspect()) == 1
    assert _record(caplog)["code"] == RefusalCode.SOURCE_NOT_IMPORTED


def test_a_freeze_through_a_linked_folder_into_the_root_stamps_it(
    tmp_path: Path,
    pack: object,
    rotated_clip: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "data"
    (root / "labels").mkdir(parents=True)
    link = tmp_path / "into-root"
    link.symlink_to(root / "labels", target_is_directory=True)
    monkeypatch.setenv("DATA_DIR", str(root))
    caplog.set_level(logging.INFO)
    folder = tmp_path / "inputs"
    _inputs(folder, pack, rotated_clip)

    assert main(_freeze(folder, rotated_clip, link)) == 0
    assert (root / STAMP_NAME).is_file()


def test_a_freeze_by_the_real_path_of_a_linked_root_stamps_it(
    tmp_path: Path,
    pack: object,
    rotated_clip: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    real = tmp_path / "real-data"
    real.mkdir()
    (tmp_path / "data").symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    caplog.set_level(logging.INFO)
    folder = tmp_path / "inputs"
    _inputs(folder, pack, rotated_clip)

    assert main(_freeze(folder, rotated_clip, real)) == 0
    assert (real / STAMP_NAME).is_file()


def test_a_root_with_unstamped_evidence_refuses_the_freeze_before_writing(
    tmp_path: Path,
    pack: object,
    rotated_clip: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    folder = tmp_path / "inputs"
    _inputs(folder, pack, rotated_clip)
    monkeypatch.delenv("DATA_DIR", raising=False)
    caplog.set_level(logging.INFO)
    # A sealed revision written outside any root, then copied in without a stamp.
    assert main(_freeze(folder, rotated_clip, tmp_path / "elsewhere")) == 0
    (root / "old-revision.json").write_bytes((tmp_path / "elsewhere/revision.json").read_bytes())
    monkeypatch.setenv("DATA_DIR", str(root))

    assert main(_freeze(folder, rotated_clip, root / "new")) == 1
    record = _record(caplog)
    assert record["code"] == RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert "remedy" in record["details"]
    assert not (root / "new").exists()
    assert not (root / STAMP_NAME).exists()


def test_a_freeze_outside_the_root_writes_no_stamp(
    tmp_path: Path,
    pack: object,
    rotated_clip: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    # Unstamped evidence in the root does not concern a write that stays outside it.
    (root / "unrelated.json").write_text('{"kind": "x", "manifest_sha256": "y"}', encoding="ascii")
    monkeypatch.setenv("DATA_DIR", str(root))
    caplog.set_level(logging.INFO)
    folder = tmp_path / "inputs"
    _inputs(folder, pack, rotated_clip)

    assert main(_freeze(folder, rotated_clip, tmp_path / "standalone")) == 0
    assert (tmp_path / "standalone/revision.json").is_file()
    assert not (root / STAMP_NAME).exists()
    assert not (tmp_path / "standalone" / STAMP_NAME).exists()
