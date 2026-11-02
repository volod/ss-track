import json
import stat
from pathlib import Path

import pytest

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sealed import (
    SEAL_FIELD,
    canonical_json,
    copy_with_sha256,
    read_sealed,
    seal,
    sha256_bytes,
    sha256_file,
    write_sealed,
)

BODY = {"kind": "test-record", "b": [1, None], "a": "value"}


def test_canonical_json_ignores_key_order() -> None:
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})


def test_canonical_json_refuses_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="JSON compliant"):
        canonical_json({"value": float("nan")})


def test_seal_covers_every_field() -> None:
    assert seal(BODY)[SEAL_FIELD] != seal(BODY | {"a": "other"})[SEAL_FIELD]


def test_written_record_reads_back_read_only(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "record.json"

    write_sealed(path, seal(BODY))

    assert read_sealed(path, "test-record") == seal(BODY)
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    assert [item.name for item in path.parent.iterdir()] == ["record.json"]


def test_copy_hashes_the_copied_bytes(tmp_path: Path) -> None:
    source = tmp_path / "a"
    source.write_bytes(b"payload")

    digest, size = copy_with_sha256(source, tmp_path / "b")

    assert (digest, size) == (sha256_bytes(b"payload"), 7)
    assert sha256_file(tmp_path / "b") == digest


def test_copy_never_overwrites(tmp_path: Path) -> None:
    (tmp_path / "a").write_bytes(b"x")
    (tmp_path / "b").write_bytes(b"y")

    with pytest.raises(FileExistsError):
        copy_with_sha256(tmp_path / "a", tmp_path / "b")


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("not json", id="not-json"),
        pytest.param("[1]", id="not-an-object"),
        pytest.param(json.dumps({"kind": "other"}), id="wrong-kind"),
        pytest.param(json.dumps(seal(BODY) | {"a": "edited"}), id="edited"),
        pytest.param(json.dumps(BODY), id="unsealed"),
    ],
)
def test_damaged_records_are_refused(tmp_path: Path, content: str) -> None:
    path = tmp_path / "record.json"
    path.write_text(content, encoding="ascii")

    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(path, "test-record")

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_missing_record_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(tmp_path / "absent.json", "test-record")

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
