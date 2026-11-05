"""One source is decoded once, however many streams a corpus cuts it into."""

import json
import shutil
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
)
from ss_track.corpus.bundles import bundle_writer
from ss_track.corpus.decoding.decode import FrameConsumer, MediaInspection, inspect_media
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from tests.corpus._media import HEIGHT, WIDTH
from tests.corpus.bundles._bundle_writing import CORPUS
from tests.corpus.conftest import HEAD, TAIL, WriteCorpus, reseal, stream_of

_FRAME_BYTES = WIDTH * HEIGHT * 3


class _Decodes:
    """Counts strict decodes while still performing them."""

    def __init__(self) -> None:
        self.paths: list[Path] = []

    def __call__(
        self, path: Path, policy: DecodePolicy, on_frame: FrameConsumer | None = None
    ) -> MediaInspection:
        self.paths.append(Path(path))
        if on_frame is None:
            return inspect_media(path, policy)
        return inspect_media(path, policy, on_frame)


class _FailAfter:
    """Performs the first decodes, then fails before another source is read."""

    def __init__(self, succeed: int) -> None:
        self.limit: int | None = succeed
        self.calls = 0

    def __call__(
        self, path: Path, policy: DecodePolicy, on_frame: FrameConsumer | None = None
    ) -> MediaInspection:
        self.calls += 1
        if self.limit is not None and self.calls > self.limit:
            raise OSError(28, "No space left on device")
        if on_frame is None:
            return inspect_media(path, policy)
        return inspect_media(path, policy, on_frame)


def _watch(monkeypatch: pytest.MonkeyPatch, decoder: _Decodes | _FailAfter) -> None:
    monkeypatch.setattr(bundle_writer, "inspect_media", decoder)


def _frames(data_root: Path, corpus: str = CORPUS) -> Path:
    return data_root / "corpus" / corpus / "frames"


def _scratch(data_root: Path, corpus: str = CORPUS) -> list[Path]:
    return list(_frames(data_root, corpus).glob(".incoming-*"))


def _remove_bundle(path: Path) -> None:
    path.chmod(0o755)
    for child in path.iterdir():
        child.chmod(0o644)
    shutil.rmtree(path)


def _cut(imported: ImportResult) -> list[dict[str, object]]:
    return [
        stream_of(imported, stream_id="head", selection=HEAD),
        stream_of(imported, stream_id="tail", selection=TAIL),
    ]


def _hashes(data_root: Path, corpus: str) -> dict[str, str]:
    staged = stage_corpus(corpus, data_root)
    return {bundle.stream_id: bundle.bundle_sha256 for bundle in staged.bundles}


def test_encounters_of_one_source_share_one_decode_and_match_solo_bundles(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passing stage has matched the import's full frame list, so the one call read it all."""
    cuts = _cut(imported)
    build_corpus(write_corpus(cuts), data_root)
    build_corpus(write_corpus([cuts[0]], corpus_id="head-only"), data_root)
    build_corpus(write_corpus([cuts[1]], corpus_id="tail-only"), data_root)
    decodes = _Decodes()
    _watch(monkeypatch, decodes)

    staged = stage_corpus(CORPUS, data_root)

    assert len(decodes.paths) == 1
    assert [bundle.stream_id for bundle in staged.bundles] == ["head", "tail"]
    assert _hashes(data_root, "head-only") == {"head": staged.bundles[0].bundle_sha256}
    assert _hashes(data_root, "tail-only") == {"tail": staged.bundles[1].bundle_sha256}
    grouped = _frames(data_root) / "head" / "00000000.rgb24"
    solo = _frames(data_root, "head-only") / "head" / "00000000.rgb24"
    assert grouped.read_bytes() == solo.read_bytes()
    assert not (_frames(data_root) / "head" / "00000008.rgb24").exists()
    decodes.paths.clear()
    assert stage_corpus(CORPUS, data_root).status == "unchanged"
    assert decodes.paths == []


def test_distinct_sources_are_decoded_once_each_when_one_is_cut_apart(
    first: ImportResult,
    second: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    streams = [
        stream_of(first, stream_id="a", selection=HEAD),
        stream_of(second, stream_id="b"),
        stream_of(first, stream_id="c", selection=TAIL),
    ]
    build_corpus(write_corpus(streams), data_root)
    for stream in streams:
        build_corpus(write_corpus([stream], corpus_id=f"solo-{stream['stream_id']}"), data_root)
    decodes = _Decodes()
    _watch(monkeypatch, decodes)

    staged = stage_corpus(CORPUS, data_root)

    assert len(decodes.paths) == 2
    assert len(set(decodes.paths)) == 2
    grouped = {bundle.stream_id: bundle.bundle_sha256 for bundle in staged.bundles}
    assert grouped == {
        "a": _hashes(data_root, "solo-a")["a"],
        "b": _hashes(data_root, "solo-b")["b"],
        "c": _hashes(data_root, "solo-c")["c"],
    }


def test_a_failed_frame_write_publishes_no_bundle_of_that_source(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_corpus(write_corpus(_cut(imported)), data_root)
    written: list[Path] = []
    write_bytes = Path.write_bytes
    head_frames = HEAD["end_frame"] - HEAD["start_frame"]

    def fail_on_the_next_stream(path: Path, data: bytes) -> int:
        if path.suffix == ".rgb24":
            written.append(path)
            if len(written) == head_frames + 1:
                raise OSError(28, "No space left on device")
        return write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_on_the_next_stream)

    with pytest.raises(OSError, match="No space left"):
        stage_corpus(CORPUS, data_root)

    assert not (_frames(data_root) / "head").exists()
    assert not (_frames(data_root) / "tail").exists()
    assert _scratch(data_root) == []


@pytest.mark.parametrize(
    "error",
    [OSError(18, "Invalid cross-device link"), KeyboardInterrupt()],
    ids=["rename-fails", "interrupted"],
)
def test_a_stopped_rename_removes_bundles_already_published_in_that_pass(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
) -> None:
    build_corpus(write_corpus(_cut(imported)), data_root)
    rename = Path.rename

    def fail_tail(path: Path, target: Path) -> Path:
        if target.name == "tail":
            raise error
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_tail)

    with pytest.raises(type(error)):
        stage_corpus(CORPUS, data_root)

    assert not (_frames(data_root) / "head").exists()
    assert not (_frames(data_root) / "tail").exists()
    assert _scratch(data_root) == []


def test_a_source_finished_before_the_refusal_stays_staged(
    first: ImportResult,
    second: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    streams = [
        stream_of(first, stream_id="a", selection=HEAD),
        stream_of(second, stream_id="b"),
        stream_of(first, stream_id="c", selection=TAIL),
    ]
    build_corpus(write_corpus(streams), data_root)
    failing = _FailAfter(1)
    _watch(monkeypatch, failing)

    with pytest.raises(OSError, match="No space left"):
        stage_corpus(CORPUS, data_root)

    frames = _frames(data_root)
    assert (frames / "a").is_dir()
    assert (frames / "c").is_dir()
    assert not (frames / "b").exists()
    assert not (frames.parent / "frame-set.json").exists()
    assert _scratch(data_root) == []
    failing.limit = None
    failing.calls = 0

    result = stage_corpus(CORPUS, data_root)

    assert failing.calls == 1
    assert {bundle.stream_id: bundle.status for bundle in result.bundles} == {
        "a": "unchanged",
        "b": "staged",
        "c": "unchanged",
    }


def test_replacing_one_missing_stream_decodes_that_source_once(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_corpus(write_corpus(_cut(imported)), data_root)
    original = _hashes(data_root, CORPUS)
    _remove_bundle(_frames(data_root) / "tail")
    decodes = _Decodes()
    _watch(monkeypatch, decodes)

    result = stage_corpus(CORPUS, data_root)

    assert len(decodes.paths) == 1
    assert {bundle.stream_id: bundle.bundle_sha256 for bundle in result.bundles} == original
    assert {bundle.stream_id: bundle.status for bundle in result.bundles} == {
        "head": "unchanged",
        "tail": "staged",
    }


def test_too_little_space_for_every_pending_stream_refuses_before_decoding(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_corpus(write_corpus(_cut(imported)), data_root)
    frames = (HEAD["end_frame"] - HEAD["start_frame"]) + (TAIL["end_frame"] - TAIL["start_frame"])
    required = _FRAME_BYTES * frames
    usage = shutil.disk_usage(data_root)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: usage._replace(free=required - 1))
    decodes = _Decodes()
    _watch(monkeypatch, decodes)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.STORAGE_FAILED
    assert caught.value.details["required_bytes"] == required
    assert decodes.paths == []
    assert _scratch(data_root) == []


def test_decode_drift_names_every_stream_of_the_pass_and_publishes_none(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    record = json.loads(imported.manifest_path.read_text(encoding="ascii"))
    sequence = record["sequence"] | {"pts": [pts + 1 for pts in record["sequence"]["pts"]]}
    reseal(imported.manifest_path, sequence=sequence)
    build_corpus(write_corpus(_cut(imported)), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.DECODE_DRIFT
    assert caught.value.details["fields"] == ["pts"]
    assert caught.value.details["stream_ids"] == ["head", "tail"]
    assert not (_frames(data_root) / "head").exists()
    assert not (_frames(data_root) / "tail").exists()
    assert _scratch(data_root) == []
