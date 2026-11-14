"""The interactive selection pass reviews every selected window into the run's own review."""

import io
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

import pytest
import yaml

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.review import pass_interactive
from ss_track.corpus.review.decisions import read_review
from ss_track.corpus.review.export import export_review
from ss_track.corpus.review.pass_interactive import _renderer, conduct_pass, open_pass
from ss_track.corpus.review.pass_session import load_pass, pass_target
from ss_track.corpus.review.queue import Offered
from tests.corpus.conftest import last_record
from tests.corpus.review._review import RUN_ID, STOCK_DECISIONS, write_review


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 40.0
        return self.now


def _session(
    data_root: Path, review: Path, text: str, seen: list[str], reviewer: str = "second reviewer"
) -> str:
    target = pass_target(RUN_ID, data_root)
    draft = load_pass(target, review, reviewer)
    output = io.StringIO()

    def render(window: Offered) -> list[Path]:
        seen.append(window.candidate_id)
        return [review.parent / "000.png"]

    tools = (lambda title, pictures, difference: True, lambda folder: True, render)
    conduct_pass(
        open_pass(target, review, draft, (io.StringIO(text), output), tools, _Clock()), True
    )
    return output.getvalue()


def test_the_pass_saves_resumes_and_keeps_the_decisions(
    pool: Any, data_root: Path, media: Path
) -> None:
    del pool
    review = write_review(media / "review.yaml", *STOCK_DECISIONS)
    before = read_review(review).decisions
    seen: list[str] = []
    shown = _session(data_root, review, "t\nq\n", seen)
    assert "Selection pass" in shown and "Window 2/2" in shown
    first = read_review(review)
    assert first.decisions == before
    assert first.selection_pass is not None and len(first.selection_pass.observations) == 1

    _session(data_root, review, "u\nq\n", seen)
    done = read_review(review)
    assert done.selection_pass is not None
    assert sorted(done.selection_pass.observations.values()) == ["target_present", "unknown"]
    assert done.selection_pass.reviewer_minutes is not None
    assert done.decisions == before
    export_review(review, "frozen-pass", media / "frozen.yaml", data_root)  # the pass is valid

    untouched = review.read_bytes()
    _session(data_root, review, "q\n", seen)
    assert review.read_bytes() == untouched
    _session(data_root, review, "c\nq\n", seen)
    cleared = read_review(review).selection_pass
    assert cleared is not None and len(cleared.observations) == 1


def test_another_reviewer_run_or_window_is_refused(pool: Any, data_root: Path, media: Path) -> None:
    del pool
    review = write_review(media / "review.yaml", *STOCK_DECISIONS)
    _session(data_root, review, "t\nq\n", [])
    with pytest.raises(CorpusRefusal) as other_reviewer:
        _session(data_root, review, "q\n", [], reviewer="someone else")
    assert other_reviewer.value.code is RefusalCode.IMPORT_CONFLICT

    document = yaml.safe_load(review.read_text(encoding="ascii"))
    document["selection_pass"]["windows"][0]["candidate_id"] = "pool-999"
    review.write_text(yaml.safe_dump(document), encoding="ascii")
    with pytest.raises(CorpusRefusal) as stray:
        _session(data_root, review, "q\n", [])
    assert stray.value.code is RefusalCode.MANIFEST_INVALID

    other = write_review(media / "other.yaml", *STOCK_DECISIONS, run_id="another-run")
    with pytest.raises(CorpusRefusal) as other_run:
        load_pass(pass_target(RUN_ID, data_root), other, "second reviewer")
    assert other_run.value.code is RefusalCode.MANIFEST_INVALID


def test_windows_render_one_at_a_time(
    pool: Any, data_root: Path, media: Path, tmp_path: Path
) -> None:
    del pool
    target = pass_target(RUN_ID, data_root)
    render = _renderer(target, data_root, tmp_path / "scratch")
    first, second = target.windows
    pictures = render(first)
    assert len(pictures) == first.end_frame - first.start_frame
    assert pictures[0].read_bytes().startswith(b"\x89PNG")
    assert render(first) == pictures
    render(second)
    assert not pictures[0].parent.exists()


def test_the_command_reports_its_review_file(
    pool: Any,
    data_root: Path,
    media: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del pool
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("DATA_DIR", str(data_root))
    review = write_review(media / "review.yaml", *STOCK_DECISIONS)
    played: list[int] = []

    @contextmanager
    def terminal(purpose: str) -> Iterator[tuple[TextIO, TextIO]]:
        assert purpose == "selection pass"
        yield io.StringIO("a\nf\nq\n"), io.StringIO()

    def play(title: str, pictures: list[Path], difference: bool) -> bool:
        played.append(len(pictures))
        return True

    monkeypatch.setattr(pass_interactive, "controlling_terminal", terminal)
    monkeypatch.setattr(pass_interactive, "play_flipbook", play)
    command = ["discover", "review-pass", "--run-id", RUN_ID, "--review", str(review)]
    assert main([*command, "--reviewer", "second reviewer"]) == 0
    assert last_record(caplog) == {"status": "recorded", "record_path": str(review)}
    assert len(played) == 2 and all(count > 0 for count in played)
    selection_pass = read_review(review).selection_pass
    assert selection_pass is not None
    assert sorted(selection_pass.observations.values()) == ["confuser", "target_absent"]
