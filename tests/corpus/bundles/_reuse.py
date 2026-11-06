"""Shared setup for staging a later corpus version from an earlier one."""

import json
import shutil
from collections.abc import Callable, Mapping
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
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations
from tests.corpus.conftest import WriteCorpus, stream_of

V0 = "pilot-v0"
V1 = "pilot-v1"
V2 = "pilot-v2"
FRESH = "pilot-fresh"
LATER = {"start_frame": 8, "end_frame": 16}


class Decodes:
    """Counts strict decodes while still performing them."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self,
        path: Path,
        policy: DecodePolicy,
        on_frame: FrameConsumer | None = None,
        *,
        video_stream_index: int | None = None,
    ) -> MediaInspection:
        self.calls += 1
        if on_frame is None:
            return inspect_media(path, policy, video_stream_index=video_stream_index)
        return inspect_media(path, policy, on_frame, video_stream_index=video_stream_index)


def watch(monkeypatch: pytest.MonkeyPatch) -> Decodes:
    """Count decodes performed by bundle staging."""
    decoder = Decodes()
    monkeypatch.setattr(bundle_writer, "inspect_media", decoder)
    return decoder


def stage_version(
    write_corpus: WriteCorpus,
    data_root: Path,
    imported: ImportResult,
    corpus_id: str,
    *,
    supersedes: str | None = None,
    stream_id: str = "one",
    selection: dict[str, int] | None = None,
) -> None:
    """Build one corpus version of one stream. The caller stages it."""
    fields: dict[str, object] = {"stream_id": stream_id}
    if selection is not None:
        fields["selection"] = selection
    extra: dict[str, object] = {"corpus_id": corpus_id}
    if supersedes is not None:
        extra["supersedes"] = supersedes
    build_corpus(write_corpus([stream_of(imported, **fields)], **extra), data_root)


def frames(data_root: Path, corpus_id: str, stream_id: str) -> list[Path]:
    """Return one bundle's frame files in presentation order."""
    directory = data_root / "corpus" / corpus_id / "frames" / stream_id
    return sorted(directory.glob("*.rgb24"))


def inodes(paths: list[Path]) -> set[tuple[int, int]]:
    """Return the files' identities, so a hard link is one entry."""
    return {(path.stat().st_dev, path.stat().st_ino) for path in paths}


def identity(path: Path) -> tuple[object, str]:
    """Return a bundle's identity block and bundle hash."""
    record = json.loads(path.read_text(encoding="ascii"))
    return record["identity"], record["bundle_sha256"]


def remove_version(data_root: Path, corpus_id: str) -> None:
    """Remove one version without changing the mode of frames another version links."""
    root = data_root / "corpus" / corpus_id
    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted(directories, reverse=True):
        directory.chmod(0o755)
    shutil.rmtree(root)


def conforms(record: Mapping[str, object]) -> None:
    """Require one command result to match the newest command contract."""
    contracts = load_contract_set()
    contract = contracts.named("result/command")
    frozen = contract.versions[-1]
    schema = contracts.frozen_schema(contract, frozen)
    document = json.loads(json.dumps(record))
    assert not violations(document, schema, contracts.schema_registry())


def refused(action: Callable[[], object], code: RefusalCode) -> CorpusRefusal:
    """Run an action and return the refusal of `code` it raises."""
    with pytest.raises(CorpusRefusal) as caught:
        action()
    assert caught.value.code is code
    return caught.value


def stage_kept(write_corpus: WriteCorpus, data_root: Path, imported: ImportResult) -> None:
    """Stage one version so a successor can reuse it."""
    stage_version(write_corpus, data_root, imported, V1)
    stage_corpus(V1, data_root)
