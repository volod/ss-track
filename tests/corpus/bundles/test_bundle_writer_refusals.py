"""Staging refuses a changed or disagreeing source, and leaves no bundle when it cannot finish."""

import json
import shutil
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus, stage_corpus
from tests.corpus._media import FRAME_COUNT, HEIGHT, WIDTH
from tests.corpus.bundles._bundle_writing import CORPUS, bundle_dir
from tests.corpus.conftest import WriteCorpus, reseal, stream_of


def _refused(data_root: Path, code: RefusalCode, corpus: str = CORPUS) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(corpus, data_root)
    assert caught.value.code is code
    return caught.value


def _scratch(data_root: Path) -> list[Path]:
    return list(bundle_dir(data_root).parent.glob(".incoming-*"))


@pytest.fixture
def built(imported: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> ImportResult:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    return imported


def test_changed_stored_source_is_refused(built: ImportResult, data_root: Path) -> None:
    stored = built.manifest_path.parent / "source.mkv"
    stored.chmod(0o644)
    stored.write_bytes(stored.read_bytes() + b"\x00")

    _refused(data_root, RefusalCode.SOURCE_HASH_MISMATCH)

    assert not bundle_dir(data_root).exists()


def test_a_source_redecoded_after_the_build_is_refused(
    built: ImportResult, data_root: Path
) -> None:
    reseal(built.manifest_path, decode_policy_sha256="d" * 64)

    _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)

    assert not bundle_dir(data_root).exists()


def test_a_decode_that_disagrees_with_the_import_record_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    record = json.loads(imported.manifest_path.read_text(encoding="ascii"))
    sequence = record["sequence"] | {"pts": [pts + 1 for pts in record["sequence"]["pts"]]}
    reseal(imported.manifest_path, sequence=sequence)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    refusal = _refused(data_root, RefusalCode.DECODE_DRIFT)

    assert refusal.details["fields"] == ["pts"]
    assert refusal.details["stream_id"] == "one"
    assert not bundle_dir(data_root).exists()
    assert not _scratch(data_root)


def test_a_failed_write_leaves_no_bundle_and_no_scratch(
    built: ImportResult, data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written = []
    write_bytes = Path.write_bytes

    def fail_on_third(path: Path, data: bytes) -> int:
        written.append(path)
        if len(written) == 3:
            raise OSError(28, "No space left on device")
        return write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_on_third)

    with pytest.raises(OSError, match="No space left"):
        stage_corpus(CORPUS, data_root)

    assert not bundle_dir(data_root).exists()
    assert not _scratch(data_root)


def test_too_little_free_space_is_refused_before_decoding(
    built: ImportResult, data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = shutil.disk_usage(data_root)
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: usage._replace(free=WIDTH * HEIGHT * 3 * FRAME_COUNT - 1)
    )

    refusal = _refused(data_root, RefusalCode.STORAGE_FAILED)

    assert refusal.details["required_bytes"] == WIDTH * HEIGHT * 3 * FRAME_COUNT
    assert not _scratch(data_root)
