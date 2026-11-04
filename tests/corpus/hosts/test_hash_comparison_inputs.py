"""A comparison refuses records it cannot compare: other questions, a broken seal, another schema."""

from pathlib import Path

import pytest

from ss_track.corpus import RefusalCode, record_staged_hashes
from ss_track.corpus.hosts.hash_comparison import HASH_COMPARISON_NAME
from ss_track.corpus.hosts.host_hashes import STAGED_HASHES_NAME
from tests.corpus.conftest import WriteCorpus, WriteRecording
from tests.corpus.hosts._host_hashes import (
    CORPUS,
    OTHER_HASH,
    RUN,
    Change,
    compare_refusal,
    declare_and_stage,
    other_host,
)


@pytest.fixture
def declared(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> tuple[Path, Path]:
    return declare_and_stage(write_recording, write_corpus, data_root)


@pytest.fixture
def left(declared: tuple[Path, Path], data_root: Path) -> Path:
    return record_staged_hashes(CORPUS, RUN, data_root).record_path


@pytest.mark.parametrize(
    ("change", "unmatched"),
    [
        pytest.param(lambda r: r.update(corpus_id="pilot-v2"), "corpus_id", id="corpus"),
        pytest.param(
            lambda r: r.update(decode_policy_sha256=OTHER_HASH),
            "decode_policy_sha256",
            id="decoder",
        ),
        pytest.param(
            lambda r: r["sources"][0].update(source_sha256=OTHER_HASH), "sources", id="sources"
        ),
        pytest.param(lambda r: r["bundles"].pop(), "bundles", id="bundles"),
    ],
)
def test_records_of_different_questions_are_refused_and_nothing_is_kept(
    left: Path, data_root: Path, tmp_path: Path, change: Change, unmatched: str
) -> None:
    other = other_host(left, tmp_path, change)

    refusal = compare_refusal(left, other, data_root)

    assert refusal.code is RefusalCode.HASHES_NOT_COMPARABLE
    assert refusal.details["unmatched"] == [unmatched]
    assert not (data_root / "run" / RUN / HASH_COMPARISON_NAME).exists()


def test_a_changed_record_is_refused_by_its_seal(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = tmp_path / STAGED_HASHES_NAME
    other.write_text(left.read_text(encoding="ascii").replace("mjpeg", "h264"), encoding="ascii")

    assert compare_refusal(left, other, data_root).code is RefusalCode.RECORD_TAMPERED


def test_a_record_of_another_schema_is_refused(left: Path, data_root: Path, tmp_path: Path) -> None:
    other = other_host(left, tmp_path, lambda record: record.update(schema_version=99))

    assert compare_refusal(left, other, data_root).code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_a_sealed_record_with_a_field_missing_is_refused(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = other_host(left, tmp_path, lambda record: record.pop("sources"))

    assert compare_refusal(left, other, data_root).code is RefusalCode.RECORD_TAMPERED
