"""The interactive audit review sees only the packet and leaves a review unblind accepts."""

import io
import logging
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

import pytest
import yaml

from ss_track.cli import main
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import AUDIT_BLINDING
from ss_track.corpus.review import audit_interactive, audit_viewer
from ss_track.corpus.review.audit_interactive import conduct_audit, open_session
from ss_track.corpus.review.audit_session import load_draft, read_packet
from ss_track.corpus.review.blind import present_audit, unblind_audit
from ss_track.corpus.review.blind_review import read_audit_review
from ss_track.corpus.review.decisions import read_review
from ss_track.corpus.review.review_terminal import IDLE_CAP_SECONDS
from ss_track.corpus.storage.layout import blinding_path
from tests.corpus.conftest import last_record
from tests.corpus.review._review import RUN_ID

_ITEMS = ("item-000", "item-001", "item-002")


def _packet(root: Path, audit_id: str = "audit-1") -> Path:
    observations = [{"item_id": item, "decision": "unreviewed"} for item in _ITEMS]
    template = {
        "schema_version": 1,
        "audit_id": audit_id,
        "reviewer": "",
        "independence": "not_declared",
        "blinding": "not_declared",
        "observations": observations,
    }
    root.mkdir(parents=True)
    (root / "review.yaml").write_text(yaml.safe_dump(template), encoding="ascii")
    for item in _ITEMS:
        folder = root / "items" / item
        folder.mkdir(parents=True)
        for offset in range(2):
            (folder / f"{offset:03d}.png").write_bytes(b"png")
    return root


class _Clock:
    def __init__(self, step: float) -> None:
        self.now, self.step = 0.0, step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def _review(
    packet: Path,
    text: str,
    *,
    reviewer: str = "site lead",
    step: float = 30.0,
    autoplay: bool = True,
    played: list[tuple[str, bool]] | None = None,
    blinding: str | None = None,
) -> str:
    seen = played if played is not None else []
    review = packet / "review-completed.yaml"
    loaded = read_packet(packet)
    draft = load_draft(loaded, review, reviewer, None, blinding)
    output = io.StringIO()

    def view(item_id: str, pictures: list[Path], difference: bool) -> bool:
        assert [path.name for path in pictures] == ["000.png", "001.png"]
        seen.append((item_id, difference))
        return True

    session = open_session(
        loaded, review, draft, (io.StringIO(text), output), view, lambda path: False, _Clock(step)
    )
    conduct_audit(session, autoplay)
    return output.getvalue()


def test_decisions_save_resume_and_stay_a_valid_review(tmp_path: Path) -> None:
    packet = _packet(tmp_path / "packet")
    played: list[tuple[str, bool]] = []
    text = "d\nt\nx\nf\no\n\nglare on water\np\ne\n\u00e9\nkept\nn\nq\n"
    shown = _review(packet, text, played=played, blinding="declared")
    assert "Blinded audit review" in shown and "The reason other needs a note" in shown
    assert "Use ASCII for the note" in shown and "Item 3/3: item-002" in shown
    assert played == [
        ("item-000", False),
        ("item-000", True),
        ("item-001", False),
        ("item-002", False),
        ("item-002", False),
    ]

    review = read_audit_review(packet / "review-completed.yaml")
    first, second, third = (review.observations[item] for item in _ITEMS)
    assert (first.decision, first.observation) == ("include", "target_present")
    assert (second.decision, second.observation, second.reason) == ("exclude", "confuser", "other")
    assert second.note == "kept"
    assert third.decision == "unreviewed"
    assert (review.reviewer, review.blinding, review.independence) == (
        "site lead",
        "declared",
        "not_declared",
    )
    minutes = review.reviewer_minutes
    assert minutes > 0

    resumed = _review(packet, "p\nc\ne\nq\n", autoplay=False)
    assert "Item 3/3: item-002" in resumed.split("Action")[0]
    assert "Decide the item before adding a note" in resumed
    again = read_audit_review(packet / "review-completed.yaml")
    assert again.observations["item-001"].decision == "unreviewed"
    assert again.blinding == "declared"
    assert again.reviewer_minutes >= minutes


def test_idle_time_is_capped_and_unknown_input_changes_nothing(tmp_path: Path) -> None:
    packet = _packet(tmp_path / "packet")
    shown = _review(packet, "z\nx\nw\n\nj\n9\n", step=10 * IDLE_CAP_SECONDS)
    assert "Unknown action" in shown and "Nothing changed" in shown
    review = read_audit_review(packet / "review-completed.yaml")
    assert all(item.decision == "unreviewed" for item in review.observations.values())
    assert review.reviewer_minutes * 60 == 7 * IDLE_CAP_SECONDS  # seven answers, each capped


def test_another_reviewer_or_packet_is_refused(tmp_path: Path) -> None:
    packet = _packet(tmp_path / "packet")
    _review(packet, "u\nq\n")
    with pytest.raises(CorpusRefusal) as other_reviewer:
        _review(packet, "q\n", reviewer="someone else")
    assert other_reviewer.value.code is RefusalCode.IMPORT_CONFLICT
    other = _packet(tmp_path / "other", audit_id="audit-2")
    (other / "review-completed.yaml").write_bytes((packet / "review-completed.yaml").read_bytes())
    with pytest.raises(CorpusRefusal) as other_packet:
        _review(other, "q\n")
    assert other_packet.value.code is RefusalCode.IMPORT_CONFLICT
    for picture in (packet / "items" / "item-001").iterdir():
        picture.unlink()
    with pytest.raises(CorpusRefusal) as missing:
        read_packet(packet)
    assert missing.value.code is RefusalCode.MANIFEST_INVALID


def test_a_session_on_a_presented_packet_unblinds(pool: Any, data_root: Path, media: Path) -> None:
    del pool
    packet = media / "packet"
    present_audit("audit-1", [RUN_ID], packet, data_root)
    loaded = read_packet(packet)
    review = packet / "review-completed.yaml"
    draft = load_draft(loaded, review, "site lead", "not_declared", "declared")
    streams = (io.StringIO("u\nt\nq\n"), io.StringIO())
    session = open_session(loaded, review, draft, streams, lambda *a: True, lambda p: True)
    conduct_audit(session, autoplay=False)

    result = unblind_audit("audit-1", review, media / "mapped", data_root)
    assert result.to_record()["status"] == "unblinded"
    private = read_sealed(blinding_path(data_root, "audit-1"), AUDIT_BLINDING)
    first = next(item for item in private["items"] if item["item_id"] == "item-000")
    mapped = read_review(media / "mapped" / f"{RUN_ID}.yaml")
    decision = mapped.decisions[(first["stream_id"], first["candidate_id"])]
    assert (decision.decision, decision.observation) == ("include", "unknown")
    assert mapped.blinding == "declared"


def test_the_command_reports_its_review_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    packet = _packet(tmp_path / "packet")

    @contextmanager
    def terminal(purpose: str) -> Iterator[tuple[TextIO, TextIO]]:
        assert purpose == "audit review"
        yield io.StringIO("a\nq\n"), io.StringIO()

    monkeypatch.setattr(audit_interactive, "controlling_terminal", terminal)
    monkeypatch.setattr(audit_interactive, "play_flipbook", lambda *args: True)
    command = ["discover", "review-audit", "--packet", str(packet), "--reviewer", "site lead"]
    assert main(command) == 0
    record = last_record(caplog)
    assert record == {
        "status": "recorded",
        "record_path": str(packet / "review-completed.yaml"),
    }
    observation = read_audit_review(packet / "review-completed.yaml").observations["item-000"]
    assert observation.observation == "target_absent"


def test_flipbook_loops_the_packet_pictures(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(audit_viewer.shutil, "which", lambda name: "/usr/bin/ffplay")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(audit_viewer.subprocess, "run", run)
    pictures = [Path("items/item-004/000.png"), Path("items/item-004/001.png")]
    assert audit_viewer.play_flipbook("item-004", pictures, False)
    assert audit_viewer.play_flipbook("item-004", pictures, True)
    plain, difference = seen
    assert plain[plain.index("-i") + 1] == "items/item-004/%03d.png"
    assert plain[plain.index("-loop") + 1] == "0" and "-vf" not in plain
    assert difference[difference.index("-vf") + 1].startswith("tblend=all_mode=difference")
    monkeypatch.setattr(audit_viewer.shutil, "which", lambda name: None)
    assert not audit_viewer.play_flipbook("item-004", pictures, False)
    assert not audit_viewer.reveal_folder(Path("items/item-004"))


def test_an_exclusion_takes_names_either_order_and_asks_again(tmp_path: Path) -> None:
    packet = _packet(tmp_path / "packet")
    text = "x\nquality\nmaybe\nconfuser\n\nx\nf\nzzz\nno value\n\nx\nt\n\nq\n"
    shown = _review(packet, text, autoplay=False)
    assert "Reason quality; now the observation" in shown
    assert "Enter an observation from the list" in shown
    assert "Enter a reason from the list" in shown and "Nothing changed" in shown
    review = read_audit_review(packet / "review-completed.yaml")
    first, second, third = (review.observations[item] for item in _ITEMS)
    assert (first.decision, first.observation, first.reason) == ("exclude", "confuser", "quality")
    assert (second.decision, second.observation, second.reason) == (
        "exclude",
        "confuser",
        "no_value",
    )
    assert third.decision == "unreviewed"
