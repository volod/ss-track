"""A pool refuses a selection it would have to invent or split."""

from pathlib import Path

import pytest

from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import CORPUS_POOL
from ss_track.corpus.sources.pool import prepare_pool
from ss_track.corpus.storage.layout import pool_directory
from tests.corpus.sources._pool_fixture import (
    RIGHTS,
    _declared,
    _video,
    combined_pool,
    publish,
    write_pool,
)


def test_missing_terms_and_unknown_paths_write_nothing(tmp_path: Path, data_root: Path) -> None:
    publish(
        data_root,
        "acq-one",
        "huggingface",
        "owner/dataset",
        "b" * 40,
        {"videos/a.mkv": b"plain-bytes"},
        [_video("videos/a.mkv", terms=None)],
    )
    declaration = write_pool(
        tmp_path / "pool.yaml",
        "pool-one",
        [_declared("acq-one", {"videos/a.mkv": "development"})],
    )
    with pytest.raises(CorpusRefusal) as caught:
        prepare_pool(declaration, "pool-one", data_root)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert not (data_root / "self-supervised-corpus" / "pool-one" / "pool.json").exists()

    missing = write_pool(
        tmp_path / "missing.yaml",
        "pool-missing",
        [_declared("acq-one", {"videos/missing.mkv": "development"})],
    )
    with pytest.raises(CorpusRefusal) as missing_caught:
        prepare_pool(missing, "pool-missing", data_root)
    assert missing_caught.value.code is RefusalCode.MANIFEST_INVALID


def test_same_bytes_cannot_cross_splits_or_rights(tmp_path: Path, data_root: Path) -> None:
    payload = b"same-bytes"
    _pair(data_root, payload)
    leaked = write_pool(
        tmp_path / "leak.yaml",
        "pool-leak",
        [
            _declared("acq-left", {"videos/a.mkv": "development"}),
            _declared("acq-right", {"videos/a.mkv": "calibration"}),
        ],
    )
    with pytest.raises(CorpusRefusal) as caught:
        prepare_pool(leaked, "pool-leak", data_root)
    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    assert not (data_root / "self-supervised-corpus" / "pool-leak" / "pool.json").exists()

    other = dict(RIGHTS)
    other["holder"] = "Someone Else"
    rights = write_pool(
        tmp_path / "rights.yaml",
        "pool-rights",
        [
            _declared("acq-left", {"videos/a.mkv": "development"}),
            _declared("acq-right", {"videos/a.mkv": "development"}, rights=other),
        ],
    )
    with pytest.raises(CorpusRefusal) as rights_caught:
        prepare_pool(rights, "pool-rights", data_root)
    assert rights_caught.value.code is RefusalCode.RIGHTS_CONFLICT


def test_a_changed_declaration_leaves_the_published_pool(tmp_path: Path, data_root: Path) -> None:
    declaration = combined_pool(tmp_path, data_root)
    prepare_pool(declaration, "pool-combined", data_root)
    original = (data_root / "self-supervised-corpus" / "pool-combined" / "pool.json").read_bytes()
    declaration.write_text(
        declaration.read_text(encoding="ascii").replace("calibration", "development"),
        encoding="ascii",
    )
    with pytest.raises(CorpusRefusal) as caught:
        prepare_pool(declaration, "pool-combined", data_root)
    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert (
        data_root / "self-supervised-corpus" / "pool-combined" / "pool.json"
    ).read_bytes() == original


def test_a_locked_source_withholds_footage_that_shares_its_source(
    tmp_path: Path, data_root: Path
) -> None:
    publish(
        data_root,
        "acq-rel",
        "huggingface",
        "owner/dataset",
        "e" * 40,
        {"videos/locked.mkv": b"locked", "videos/kin.mkv": b"kin", "videos/keep.mkv": b"keep"},
        [
            _video(
                "videos/locked.mkv",
                upstream_split="test_set",
                source_reference="https://example.com/shared",
            ),
            _video("videos/kin.mkv", source_reference="https://example.com/shared"),
            _video("videos/keep.mkv"),
        ],
    )
    declaration = write_pool(
        tmp_path / "related.yaml",
        "pool-rel",
        [
            _declared(
                "acq-rel",
                {
                    "videos/locked.mkv": "development",
                    "videos/kin.mkv": "development",
                    "videos/keep.mkv": "development",
                },
            )
        ],
    )
    prepare_pool(declaration, "pool-rel", data_root)
    record = read_sealed(
        data_root / "self-supervised-corpus" / "pool-rel" / "pool.json", CORPUS_POOL
    )
    rows = {(item["run_id"], item["path"]): item for item in record["videos"]}
    assert rows[("acq-rel", "videos/locked.mkv")]["status"] == "withheld_locked"
    assert rows[("acq-rel", "videos/kin.mkv")]["status"] == "withheld_related"
    recordings = list((pool_directory(data_root, "pool-rel") / "recordings").glob("*.yaml"))
    assert len(recordings) == 1
    text = recordings[0].read_text(encoding="ascii")
    assert "videos/keep.mkv" in text
    assert "videos/kin.mkv" not in text
    assert "videos/locked.mkv" not in text


def _pair(data_root: Path, payload: bytes) -> None:
    for run_id, revision in (("acq-left", "c" * 40), ("acq-right", "d" * 40)):
        publish(
            data_root,
            run_id,
            "huggingface",
            "owner/dataset",
            revision,
            {"videos/a.mkv": payload},
            [_video("videos/a.mkv", attribution=run_id)],
        )
