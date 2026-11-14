"""Terminal review of unresolved recording links, with a durable decisions checkpoint."""

import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.terminal import controlling_terminal
from ss_track.corpus.bundles.version_bundles import require_sources_hold
from ss_track.corpus.decoding.streams import recorded_video_stream_index
from ss_track.corpus.links.decisions import Decision, SourcePair, source_pair
from ss_track.corpus.links.interactive_state import (
    CHECKPOINT_NAME,
    _sync_directory,
    link_pair,
    read_checkpoint,
    save_checkpoint,
)
from ss_track.corpus.links.records import read_links
from ss_track.corpus.sources.stored import load_verified_source
from ss_track.corpus.sources.terms import evaluation_date
from ss_track.corpus.storage.layout import discovery_run_directory
from ss_track.corpus.storage.scratch import exclusive_lock
from ss_track.corpus.versions.manifests import load_corpus_manifest

INSTRUCTIONS = """Recording relationship review

A similarity is a question, not proof. Mark related only when the recordings are from the
same encounter or session; mark unrelated only when you have evidence they are independent.
Leave uncertain pairs undecided. This is not the blinded selection audit.

Controls: a/b play recording A/B; r related; u unrelated; c clear decision; n next;
p previous; j jump to pair number; h show these instructions; q save and quit.
Enter an optional ASCII evidence note after r or u. Close the video player to return here.
In ffplay, space pauses and the arrow keys seek. If ffplay is unavailable, use the shown path.
Every decision is saved immediately. Restart resumes at the first undecided pair.
"""


@dataclass(frozen=True, slots=True)
class InteractiveResult:
    """One existing command-result record for a finished or paused review."""

    run_id: str
    corpus_id: str
    checkpoint: Path
    count: int

    def to_record(self) -> dict[str, JsonValue]:
        record: dict[str, JsonValue] = {
            "status": "recorded",
            "run_id": self.run_id,
            "corpus_id": self.corpus_id,
        }
        record["manifest_path"] = str(self.checkpoint)
        return record


def _say(output: TextIO, text: str) -> None:
    output.write(text)
    output.flush()


def _ask(source: TextIO, output: TextIO, prompt: str) -> str | None:
    _say(output, prompt)
    line = source.readline()
    return None if line == "" else line.strip()


def _finish(output: TextIO, checkpoint: Path, count: int) -> int:
    _say(
        output,
        f"\nSaved {count} decision(s) in {checkpoint}.\n"
        "Use this file with discover links --decisions; related recordings must be grouped.\n",
    )
    return count


def _evidence(link: Mapping[str, Any]) -> str:
    values = []
    for item in link["evidence"]:
        extractor = f" / {item['extractor_id']}" if "extractor_id" in item else ""
        values.append(f"{item['method']}{extractor}: {item['similarity']}")
    return ", ".join(values) or "reviewer-provided link"


def _locked(link: Mapping[str, Any], identity: str) -> bool:
    return any(
        item["source_sha256"] == identity and item.get("split") == "locked"
        for item in link["sources"]
    )


def _description(link: Mapping[str, Any], identity: str, describe: Callable[[str], str]) -> str:
    return "Locked recording: playback withheld." if _locked(link, identity) else describe(identity)


def _show(
    index: int,
    links: Sequence[Mapping[str, Any]],
    decisions: Mapping[SourcePair, Decision],
    output: TextIO,
    describe: Callable[[str], str],
) -> None:
    link = links[index]
    pair = link_pair(link)
    decision = decisions.get(pair)
    count = sum(link_pair(item) in decisions for item in links)
    _say(output, f"\nPair {index + 1}/{len(links)} | decided {count}/{len(links)}\n")
    _say(output, f"A: {pair[0]}\n   {_description(link, pair[0], describe)}\n")
    _say(output, f"B: {pair[1]}\n   {_description(link, pair[1], describe)}\n")
    _say(output, f"Evidence: {_evidence(link)}\n")
    _say(output, f"Decision: {decision.decision if decision else 'undecided'}\n")
    if decision and decision.note:
        _say(output, f"Note: {decision.note}\n")


def _navigate(action: str, index: int, size: int, source: TextIO, output: TextIO) -> int | None:
    if action == "n":
        return min(index + 1, size - 1)
    if action == "p":
        return max(index - 1, 0)
    value = _ask(source, output, "Pair number: ")
    if value is None:
        return None
    if value.isascii() and value.isdigit() and len(value) <= 9 and 1 <= int(value) <= size:
        return int(value) - 1
    _say(output, "Enter a pair number in the displayed range.\n")
    return index


def _play_choice(
    link: Mapping[str, Any], identity: str, output: TextIO, play: Callable[[str], bool]
) -> None:
    if _locked(link, identity):
        _say(output, "Locked recording: playback withheld.\n")
    elif not play(identity):
        _say(output, "Could not play the recording; use the displayed path.\n")


def conduct_review(
    links: list[Mapping[str, Any]],
    reviewer: str,
    checkpoint: Path,
    source: TextIO,
    output: TextIO,
    describe: Callable[[str], str],
    play: Callable[[str], bool],
    extra_pairs: frozenset[SourcePair] = frozenset(),
) -> int:
    """Interact with injected streams and player; save each explicit change before advancing."""
    decisions = read_checkpoint(checkpoint, reviewer, links, extra_pairs)
    _say(output, INSTRUCTIONS)
    _say(output, f"Reviewer: {reviewer}\nCheckpoint: {checkpoint}\n")
    if not links:
        _say(output, "\nNo links need review.\n")
        return _finish(output, checkpoint, len(decisions))
    index = next((i for i, link in enumerate(links) if link_pair(link) not in decisions), 0)
    while True:
        _show(index, links, decisions, output, describe)
        action = _ask(source, output, "\nAction [a/b/r/u/c/n/p/j/h/q]: ")
        if action is None or action.lower() == "q":
            return _finish(output, checkpoint, len(decisions))
        position = _step(
            action.lower(), index, links, decisions, reviewer, checkpoint, source, output, play
        )
        if position is None:
            return _finish(output, checkpoint, len(decisions))
        index = position


def _change_decision(
    action: str,
    pair: SourcePair,
    decisions: dict[SourcePair, Decision],
    reviewer: str,
    checkpoint: Path,
    source: TextIO,
    output: TextIO,
) -> bool | None:
    choices = dict(decisions)
    if action == "c":
        choices.pop(pair, None)
    else:
        note = _ask(source, output, "Evidence note (optional ASCII; blank for none): ")
        if note is None:
            return None
        if not note.isascii():
            _say(output, "Use ASCII for the note; no decision was saved.\n")
            return False
        choices[pair] = Decision(pair, "related" if action == "r" else "unrelated", note or None)
    save_checkpoint(checkpoint, reviewer, choices)
    decisions.clear()
    decisions.update(choices)
    return action != "c"


def _step(
    action: str,
    index: int,
    links: list[Mapping[str, Any]],
    decisions: dict[SourcePair, Decision],
    reviewer: str,
    checkpoint: Path,
    source: TextIO,
    output: TextIO,
    play: Callable[[str], bool],
) -> int | None:
    pair = link_pair(links[index])
    if action in ("a", "b"):
        _play_choice(links[index], pair[0] if action == "a" else pair[1], output, play)
    elif action in ("r", "u", "c"):
        advance = _change_decision(action, pair, decisions, reviewer, checkpoint, source, output)
        if advance is None:
            return None
        if advance:
            return min(index + 1, len(links) - 1)
    elif action in ("n", "p", "j"):
        return _navigate(action, index, len(links), source, output)
    elif action == "h":
        _say(output, INSTRUCTIONS)
    else:
        _say(output, "Unknown action; enter h for help.\n")
    return index


def _play(path: Path, stream_index: int) -> bool:
    executable = shutil.which("ffplay")
    if executable is None:
        return False
    result = subprocess.run(
        [
            executable,
            "-autoexit",
            "-hide_banner",
            "-loglevel",
            "error",
            "-an",
            "-vst",
            f"v:{stream_index}",
            "-i",
            str(path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _describe_source(identity: str, data_root: Path) -> str:
    source = load_verified_source(identity, data_root)
    origins = source.record.get("origin")
    names = []
    if isinstance(origins, list):
        for item in origins:
            if isinstance(item, dict):
                names.append(
                    f"{item.get('provider', 'unknown')} / {item.get('collection_id', 'unknown')}"
                    f" / {item.get('video_path', 'unknown')}"
                )
    suffix = f"\n   Origin: {'; '.join(names)}" if names else ""
    stream_index = recorded_video_stream_index(source.sequence)
    return f"{source.stored} (video stream {stream_index}){suffix}"


def _validate_record(
    record: Mapping[str, Any], reviewer: str, data_root: Path
) -> list[Mapping[str, Any]]:
    if not reviewer.strip() or not reviewer.isascii():
        raise CorpusRefusal(RefusalCode.MANIFEST_INVALID, "reviewer must be nonempty ASCII")
    links: list[Mapping[str, Any]] = record["links"]
    corpus = load_corpus_manifest(str(record["corpus_id"]), data_root)
    if corpus[SEAL_FIELD] != record["corpus_manifest_sha256"]:
        raise CorpusRefusal(RefusalCode.RECORD_INVALID, "link record names a different corpus seal")
    require_sources_hold(corpus, data_root, evaluation_date(None))
    return links


def _prior_decisions(record: Mapping[str, Any], reviewer: str) -> dict[SourcePair, Decision]:
    review = record.get("review")
    if review is None:
        return {}
    if review["reviewer"] != reviewer:
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "link record names a different reviewer")
    decisions: dict[SourcePair, Decision] = {}
    for link in record["links"]:
        if "decision" in link:
            pair = link_pair(link)
            item = link["decision"]
            decisions[pair] = Decision(pair, str(item["decision"]), item.get("note"))
    for item in record["decisions_outside_links"]:
        pair = source_pair(str(item["sources"][0]), str(item["sources"][1]))
        decisions[pair] = Decision(pair, str(item["decision"]), item.get("note"))
    if len(decisions) != review["decision_count"]:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID, "link record omits or repeats prior decisions"
        )
    return decisions


def _initialize_checkpoint(
    checkpoint: Path, reviewer: str, prior: Mapping[SourcePair, Decision]
) -> None:
    if not checkpoint.exists() and not checkpoint.is_symlink():
        save_checkpoint(checkpoint, reviewer, prior)


def review_interactively(run_id: str, reviewer: str, data_root: Path) -> InteractiveResult:
    """Review a sealed link run through the controlling terminal under an exclusive lock."""
    record = read_links(data_root, run_id)
    links = _validate_record(record, reviewer, data_root)
    prior = _prior_decisions(record, reviewer)
    extra_pairs = frozenset(prior) - {link_pair(link) for link in links}
    run_dir = discovery_run_directory(data_root, run_id)
    review_dir = run_dir / "link-review"
    if review_dir.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "review directory is a symbolic link")
    review_dir.mkdir(mode=0o700, exist_ok=True)
    _sync_directory(run_dir)
    busy = CorpusRefusal(RefusalCode.DISCOVERY_IN_PROGRESS, "link review is already active")
    with exclusive_lock(review_dir, ".lock", clear=(review_dir,), busy=busy):
        descriptions: dict[str, str] = {}

        def describe(identity: str) -> str:
            if identity not in descriptions:
                descriptions[identity] = _describe_source(identity, data_root)
            return descriptions[identity]

        def play(identity: str) -> bool:
            source = load_verified_source(identity, data_root)
            return _play(source.stored, recorded_video_stream_index(source.sequence))

        checkpoint = review_dir / CHECKPOINT_NAME
        _initialize_checkpoint(checkpoint, reviewer, prior)
        with controlling_terminal("link review") as (source, output):
            count = conduct_review(
                links, reviewer, checkpoint, source, output, describe, play, extra_pairs
            )
    return InteractiveResult(run_id, str(record["corpus_id"]), checkpoint, count)
