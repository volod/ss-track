"""A combined pool keeps source identity and withholds what it cannot justify."""

from pathlib import Path

import pytest
import yaml

from ss_track.cli import main
from ss_track.corpus import build_corpus, import_source, stage_corpus, verify_corpus_frames
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.records.kinds import CORPUS_POOL
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.sources.pool import prepare_pool
from ss_track.corpus.sources.pool_account import account_corpus
from ss_track.corpus.sources.stored import load_source_record
from ss_track.corpus.storage.layout import pool_corpus_path, pool_record_path
from ss_track.corpus.versions.manifests import load_corpus_manifest
from tests.corpus.sources._pool_fixture import combined_pool


def test_two_sources_prepare_stage_and_replay(
    tmp_path: Path, data_root: Path, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    declaration = combined_pool(tmp_path, data_root)
    prepared = prepare_pool(declaration, "pool-combined", data_root)
    record = read_sealed(prepared.path, CORPUS_POOL)
    _assert_selection(record)
    _assert_hidden(pool_record_path(data_root, "pool-combined"), tmp_path)

    recordings = prepared.path.parent / "recordings"
    for path in sorted(recordings.glob("*.yaml")):
        import_source(path, data_root)
    built = build_corpus(pool_corpus_path(data_root, "pool-combined"), data_root)
    assert built.status == "built"
    assert stage_corpus("combined-v1", data_root).status == "staged"
    assert verify_corpus_frames("combined-v1", data_root).status == "verified"
    assert write_links(LinkRequest("links-combined", "combined-v1"), data_root).status == "written"
    _assert_lineage(record, data_root)

    assert (
        main(["discover", "pool", "--declaration", str(declaration), "--run-id", "pool-combined"])
        == 0
    )
    assert caplog.records[-1].getMessage().count('"status": "unchanged"') == 1
    assert (
        build_corpus(pool_corpus_path(data_root, "pool-combined"), data_root).status == "unchanged"
    )
    _build_case(record, data_root, tmp_path)
    assert account_corpus("combined-v2", data_root) == {
        "unique_stream_count": 3,
        "unique_case_count": 1,
        "collections": [
            {
                "provider": "huggingface",
                "collection_id": "owner/dataset",
                "stream_count": 2,
                "case_count": 1,
            },
            {"provider": "zenodo", "collection_id": "15696105", "stream_count": 2, "case_count": 1},
        ],
    }


def _assert_selection(record: dict[str, object]) -> None:
    rows = {(item["run_id"], item["path"]): item for item in record["videos"]}
    assert rows[("acq-zenodo", "videos/locked.mkv")]["status"] == "withheld_locked"
    assert rows[("acq-hf", "videos/conflict.mkv")]["status"] == "association_conflict"
    assert rows[("acq-zenodo", "videos/plain.mkv")]["split"] == "calibration"
    assert rows[("acq-zenodo", "videos/bird.mkv")]["association"] == "missing"
    assert rows[("acq-hf", "videos/bird.mkv")]["license"] == "cc-1.0"
    assert rows[("acq-hf", "videos/drone.mkv")]["source_reference"] == "https://example.com/drone"
    assert rows[("acq-hf", "videos/drone.mkv")]["annotation_reference"] == "annotations/drone.txt"
    accounts = {item["collection_id"]: item for item in record["accounting"]}
    assert accounts["15696105"]["included"] == 2
    assert accounts["15696105"]["withheld_locked"] == 1
    assert accounts["15696105"]["missing_metadata"] == 3
    assert accounts["owner/dataset"]["included"] == 2
    assert accounts["owner/dataset"]["association_conflict"] == 1
    assert accounts["owner/dataset"]["missing_metadata"] == 0
    bird = _bird(record)
    assert len(bird["members"]) == 2
    assert sum(len(group["streams"]) for group in record["groups"]) == 3


def _assert_hidden(path: Path, tmp_path: Path) -> None:
    text = path.read_text(encoding="ascii")
    for hidden in (
        "page=1",
        "fuzzy-license",
        "not-a-label-xyz",
        "token=abcdefsecret",
        str(tmp_path),
    ):
        assert hidden not in text
    assert "personal recordings" in text
    assert "https://example.com/unknown" in text


def _assert_lineage(record: dict[str, object], data_root: Path) -> None:
    source = load_source_record(_bird(record)["source_sha256"], data_root)
    origins = {item["provider"]: item for item in source["origin"]}
    assert source["rights"]["basis"] == "licensed"
    assert source["source"]["sha256_declared"] is True
    assert origins["huggingface"]["license"] == "cc-1.0"
    assert origins["zenodo"]["license"] is None
    assert origins["zenodo"]["annotation_reference"] == "annotations/bird.json"
    assert origins["zenodo"]["attribution"] == "Zenodo bird"
    manifest = load_corpus_manifest("combined-v1", data_root)
    for stream in manifest["streams"]:
        assert "license" not in stream and "annotation_reference" not in stream


def _build_case(record: dict[str, object], data_root: Path, tmp_path: Path) -> None:
    document = yaml.safe_load(
        pool_corpus_path(data_root, "pool-combined").read_text(encoding="ascii")
    )
    document["corpus_id"] = "combined-v2"
    document["supersedes"] = "combined-v1"
    bird = _bird(record)["stream_id"]
    for group in document["groups"]:
        for encounter in group["encounters"]:
            for stream in encounter["streams"]:
                if stream["stream_id"] == bird:
                    stream["generated_cases"] = [
                        {
                            "case_id": "bird-shake",
                            "transform": "camera_shake",
                            "seed": 1,
                            "parameters": {"amplitude": 2},
                        }
                    ]
    path = tmp_path / "combined-v2.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="ascii")
    assert build_corpus(path, data_root).status == "built"
    assert stage_corpus("combined-v2", data_root).status == "staged"
    assert verify_corpus_frames("combined-v2", data_root).status == "verified"


def _bird(record: dict[str, object]) -> dict[str, object]:
    for group in record["groups"]:
        for stream in group["streams"]:
            if len(stream["members"]) == 2:
                return stream
    raise AssertionError("the shared recording was not grouped")
