"""`discover run` writes one whole, deterministic run from a plan, and `discover verify` checks it."""

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.discovery.features import FeatureFile
from ss_track.corpus.discovery.plan import read_discovery_plan
from ss_track.corpus.discovery.reader import read_discovery, verify_discovery
from ss_track.corpus.discovery.records import DiscoveryRecords, seal_discovery, write_discovery
from ss_track.corpus.discovery.run import build_discovery, run_discovery
from ss_track.corpus.records.sealing import seal
from ss_track.corpus.storage.layout import discovery_root, discovery_run_directory
from ss_track.corpus.storage.scratch import exclusive_lock
from tests.corpus.conftest import WriteCorpus, last_record, stream_of
from tests.corpus.discovery._plan import (
    RUN_ID,
    plan_document,
    worker_environ,
    write_hints,
    write_plan,
)
from tests.corpus.siblings._fake_sibling import Caches


@pytest.fixture
def plan(
    first: ImportResult,
    second: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    media: Path,
    caches: Caches,
) -> Path:
    streams = [stream_of(first, stream_id="one"), stream_of(second, stream_id="two")]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus("pilot-v1", data_root)
    write_hints(media, first.source_sha256, 0.6, 0.61, 9.0)
    return write_plan(media, plan_document(caches))


@pytest.fixture
def environ(caches: Caches, sibling_python: Path) -> dict[str, str]:
    return worker_environ(caches, sibling_python)


def _files(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_a_plan_writes_a_whole_run_that_verifies(
    plan: Path, data_root: Path, environ: dict[str, str]
) -> None:
    result = run_discovery(plan, data_root, environ=environ)

    record: dict[str, Any] = result.to_record()
    assert record["status"] == "written" and record["inventory_count"] == 2
    assert record["feature_row_count"] == 12  # 24 frames at a stride of 4, in each stream
    assert record["hint_sources"] == [
        {
            "hint_source_id": "ss-video-1",
            "read": 4,
            "mapped": 1,
            "unmapped": [
                {"reason": "no_hash_join", "count": 1},
                {"reason": "not_on_slot", "count": 1},
                {"reason": "slot_out_of_range", "count": 1},
            ],
        }
    ]
    assert verify_discovery(data_root, RUN_ID) == result.records
    one: Any = result.records.inventories["one"]["candidates"]
    sibling = [item for item in one if item["origin"]["source"] == "sibling_time"]
    assert [item["window"] for item in sibling] == [{"start_frame": 13, "end_frame": 18}]
    assert result.records.run["source_approval"] == {
        "owner": "project owner",
        "reference": "fixture-media",
    }
    assert sorted(_files(discovery_run_directory(data_root, RUN_ID))) == [
        "features/clip-b16/one.f32",
        "features/clip-b16/one.json",
        "features/clip-b16/two.f32",
        "features/clip-b16/two.json",
        "inventories/one.json",
        "inventories/two.json",
        "run.json",
    ]


def test_a_retried_plan_writes_the_same_bytes_and_changes_nothing(
    plan: Path, data_root: Path, environ: dict[str, str]
) -> None:
    run_discovery(plan, data_root, environ=environ)
    before = _files(discovery_run_directory(data_root, RUN_ID))
    rebuilt = build_discovery(read_discovery_plan(plan), data_root, environ=environ)

    again = run_discovery(plan, data_root, environ=environ)

    assert again.status == "unchanged" and again.records == rebuilt
    assert _files(discovery_run_directory(data_root, RUN_ID)) == before


def test_another_plan_under_a_used_run_id_is_refused(
    plan: Path, data_root: Path, environ: dict[str, str], media: Path, caches: Caches
) -> None:
    run_discovery(plan, data_root, environ=environ)
    other = write_plan(media, plan_document(caches, audit={"seed": 8, "sample_size": 2}))

    with pytest.raises(CorpusRefusal) as caught:
        run_discovery(other, data_root, environ=environ)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def test_a_run_id_another_command_holds_is_refused(
    plan: Path, data_root: Path, environ: dict[str, str]
) -> None:
    held = exclusive_lock(discovery_root(data_root), f".run-{RUN_ID}.lock")
    with held, pytest.raises(CorpusRefusal) as caught:
        run_discovery(plan, data_root, environ=environ)

    assert caught.value.code is RefusalCode.DISCOVERY_IN_PROGRESS
    assert not discovery_run_directory(data_root, RUN_ID).exists()


def test_concurrent_writers_of_one_run_id_leave_one_whole_run(
    plan: Path, data_root: Path, environ: dict[str, str], media: Path, caches: Caches
) -> None:
    first = build_discovery(read_discovery_plan(plan), data_root, environ=environ)
    other_plan = write_plan(media, plan_document(caches, audit={"seed": 8, "sample_size": 1}))
    second = build_discovery(read_discovery_plan(other_plan), data_root, environ=environ)
    outcomes: list[object] = []

    def write(records: DiscoveryRecords) -> None:
        try:
            outcomes.append(write_discovery(data_root, records).written)
        except CorpusRefusal as refusal:
            outcomes.append(refusal.code)

    threads = [threading.Thread(target=write, args=(records,)) for records in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(map(str, outcomes)) == ["CORPUS_CONFLICT", "True"]
    assert read_discovery(data_root, RUN_ID) in (first, second)
    assert not list(discovery_root(data_root).glob(".incoming-*"))


def test_a_plan_without_the_owners_approval_is_refused(
    plan: Path, data_root: Path, environ: dict[str, str], media: Path, caches: Caches
) -> None:
    document = plan_document(caches)
    del document["source_approval"]

    with pytest.raises(CorpusRefusal) as caught:
        run_discovery(write_plan(media, document), data_root, environ=environ)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "source_approval" in caught.value.message


_STAMP = ("kind", "schema_version", "manifest_sha256")


def _bodies(records: DiscoveryRecords) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a sealed run's bodies as a writer passes them, for a test to change and reseal."""
    run = {
        key: value
        for key, value in records.run.items()
        if key not in (*_STAMP, "inventories", "feature_rows")
    }
    inventories = [
        json.loads(json.dumps({key: value for key, value in item.items() if key not in _STAMP}))
        for item in records.inventories.values()
    ]
    return run, inventories


def _moved_sibling(records: DiscoveryRecords) -> DiscoveryRecords:
    """Reseal the run with its sibling window one frame off, as a wrong mapping would leave it."""
    run, inventories = _bodies(records)
    for inventory in inventories:
        for candidate in inventory["candidates"]:
            if candidate["origin"]["source"] == "sibling_time":
                candidate["window"] = {"start_frame": 12, "end_frame": 17}
    return seal_discovery(run, inventories, records.features.values())


def test_a_sibling_window_the_slot_rule_does_not_give_is_refused(
    plan: Path, data_root: Path, environ: dict[str, str]
) -> None:
    moved = _moved_sibling(build_discovery(read_discovery_plan(plan), data_root, environ=environ))

    with pytest.raises(CorpusRefusal) as caught:
        write_discovery(data_root, moved)

    assert caught.value.code is RefusalCode.RECORD_INVALID
    findings: Any = caught.value.details["findings"]
    assert [(item["record"], item["rule"]) for item in findings] == [("inventories/one", "sibling")]
    assert "maps slot 3 to frames 13 to 17" in findings[0]["message"]


def test_a_changed_vector_file_is_refused_on_read(
    plan: Path, data_root: Path, environ: dict[str, str]
) -> None:
    run_discovery(plan, data_root, environ=environ)
    vectors = discovery_run_directory(data_root, RUN_ID) / "features/clip-b16/two.f32"
    vectors.chmod(0o644)
    vectors.write_bytes(bytes(len(vectors.read_bytes())))

    with pytest.raises(CorpusRefusal) as caught:
        read_discovery(data_root, RUN_ID)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_rows_that_name_other_frames_are_refused(
    plan: Path, data_root: Path, environ: dict[str, str]
) -> None:
    records = build_discovery(read_discovery_plan(plan), data_root, environ=environ)
    name = "features/clip-b16/one.json"
    feature = records.features[name]
    body: Any = json.loads(json.dumps(feature.record))
    del body["manifest_sha256"]
    body["rows"][0]["frame_sha256"] = "0" * 64
    damaged = FeatureFile(seal(body), feature.vectors)
    others = [item for key, item in records.features.items() if key != name]
    run, inventories = _bodies(records)

    with pytest.raises(CorpusRefusal) as caught:
        write_discovery(data_root, seal_discovery(run, inventories, [damaged, *others]))

    findings: Any = caught.value.details["findings"]
    assert [(item["record"], item["rule"]) for item in findings] == [(name, "binding")]


def test_the_commands_report_a_written_and_a_verified_run(
    plan: Path,
    environ: dict[str, str],
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in environ.items():
        monkeypatch.setenv(key, value)

    assert main(["discover", "run", "--plan", str(plan)]) == 0
    written = last_record(caplog)
    assert main(["discover", "verify", "--run-id", RUN_ID]) == 0
    verified = last_record(caplog)

    assert (written["status"], verified["status"]) == ("written", "verified")
    assert written["manifest_sha256"] == verified["manifest_sha256"]
    assert main(["discover", "verify", "--run-id", "absent"]) == 1
    assert json.loads(caplog.records[-1].getMessage())["code"] == "RECORD_TAMPERED"
