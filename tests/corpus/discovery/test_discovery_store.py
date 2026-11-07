"""A discovery run is written whole, read back unchanged, and bound to what its corpus staged."""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.bundles.stage_report import FramesResult
from ss_track.corpus.discovery.reader import read_discovery, verify_discovery
from ss_track.corpus.discovery.records import DiscoveryRecords, write_discovery
from ss_track.corpus.sources.importer import ImportResult
from ss_track.corpus.storage.layout import candidate_inventory_path, discovery_run_path
from tests._sealing import self_sealed
from tests.corpus.bundles._frame_set import stage_two_streams
from tests.corpus.conftest import WriteCorpus
from tests.corpus.discovery._records import RUN_ID, Bodies, bodies, staged_streams


@pytest.fixture
def staged(
    first: ImportResult, second: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> FramesResult:
    """Two staged streams, `one` and `two`, and a generated case `shaken` of `one`."""
    return stage_two_streams(first, second, write_corpus, data_root)


@pytest.fixture
def golden(staged: FramesResult, data_root: Path) -> Bodies:
    return bodies(*staged_streams(data_root))


def _refused(data_root: Path, records: DiscoveryRecords, code: RefusalCode) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        write_discovery(data_root, records)
    assert caught.value.code is code
    return caught.value


def _rules(refusal: CorpusRefusal) -> set[tuple[str, str]]:
    findings: Any = refusal.details["findings"]
    return {(item["record"], item["pointer"]) for item in findings}


def test_a_written_run_reads_back_unchanged_and_verifies(golden: Bodies, data_root: Path) -> None:
    records = golden.seal()

    written = write_discovery(data_root, records)

    assert written.written and written.path == discovery_run_path(data_root, RUN_ID)
    assert read_discovery(data_root, RUN_ID) == records
    assert verify_discovery(data_root, RUN_ID) == records
    assert sorted(path.name for path in written.path.parent.rglob("*.json")) == [
        "one.json",
        "run.json",
        "two.json",
    ]


def test_repeating_a_run_changes_nothing(golden: Bodies, data_root: Path) -> None:
    records = golden.seal()
    write_discovery(data_root, records)
    before = discovery_run_path(data_root, RUN_ID).stat().st_mtime_ns

    again = write_discovery(data_root, records)

    assert not again.written
    assert discovery_run_path(data_root, RUN_ID).stat().st_mtime_ns == before


def test_a_run_id_never_holds_other_records(golden: Bodies, data_root: Path) -> None:
    write_discovery(data_root, golden.seal())
    golden.run["selection"]["method"] = "other-rank"

    refusal = _refused(data_root, golden.seal(), RefusalCode.CORPUS_CONFLICT)

    assert refusal.details["run_id"] == RUN_ID


def test_a_run_over_another_frame_set_is_not_written(golden: Bodies, data_root: Path) -> None:
    golden.run["frame_set_sha256"] = "0" * 64

    _refused(data_root, golden.seal(), RefusalCode.FRAME_SET_MISMATCH)

    assert not discovery_run_path(data_root, RUN_ID).parent.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_manifest_sha256", "1" * 64),
        ("source_sha256", "2" * 64),
        ("bundle_sha256", "3" * 64),
        ("group_id", "group-two"),
        ("bundle_frames", {"start_frame": 0, "end_frame": 16}),
    ],
)
def test_an_inventory_repeats_what_its_corpus_staged(
    golden: Bodies, data_root: Path, field: str, value: object
) -> None:
    golden.inventory("two")[field] = value
    if field == "bundle_frames":  # keep the pool tiled, so only the binding is wrong
        golden.inventory("two")["candidates"].pop()
        golden.run["audit"]["strata"][0]["eligible_count"] -= 1
        golden.run["audit"]["strata"][0]["sample_size"] -= 1
        probability = 1 / golden.run["audit"]["strata"][0]["eligible_count"]
        for name in ("one", "two"):
            for candidate in golden.inventory(name)["candidates"]:
                if "inclusion_probability" in candidate["audit"]:
                    candidate["audit"]["inclusion_probability"] = probability

    refusal = _refused(data_root, golden.seal(), RefusalCode.RECORD_INVALID)

    assert _rules(refusal) == {("inventories/two", f"/{field}")}


def test_no_inventory_covers_a_generated_case(golden: Bodies, data_root: Path) -> None:
    golden.inventory("two")["stream_id"] = "shaken"

    refusal = _refused(data_root, golden.seal(), RefusalCode.RECORD_INVALID)

    assert ("inventories/shaken", "/stream_id") in _rules(refusal)


def _written(golden: Bodies, data_root: Path) -> Path:
    write_discovery(data_root, golden.seal())
    return candidate_inventory_path(data_root, RUN_ID, "two")


def _rewrite(path: Path, record: dict[str, Any]) -> None:
    path.chmod(0o644)
    path.write_text(json.dumps(record), encoding="ascii")


def test_an_altered_inventory_is_tampered(golden: Bodies, data_root: Path) -> None:
    path = _written(golden, data_root)
    record = json.loads(path.read_text(encoding="ascii"))
    record["candidates"][0]["selection"]["rank"] = 9
    _rewrite(path, record)

    with pytest.raises(CorpusRefusal) as caught:
        read_discovery(data_root, RUN_ID)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_a_resealed_inventory_is_not_the_one_the_run_sealed(
    golden: Bodies, data_root: Path
) -> None:
    path = _written(golden, data_root)
    record = json.loads(path.read_text(encoding="ascii"))
    record.pop("manifest_sha256")
    record["candidates"][0]["scores"][0]["value"] = 99.0
    _rewrite(path, self_sealed(record))

    with pytest.raises(CorpusRefusal) as caught:
        read_discovery(data_root, RUN_ID)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
    assert caught.value.message == "an inventory is not the one its run sealed"


def test_a_resealed_run_that_breaks_its_contract_is_invalid(
    golden: Bodies, data_root: Path
) -> None:
    write_discovery(data_root, golden.seal())
    path = discovery_run_path(data_root, RUN_ID)
    record = json.loads(path.read_text(encoding="ascii"))
    record.pop("manifest_sha256")
    del record["extractors"][0]["weights"][0]["sha256"]
    _rewrite(path, self_sealed(record))

    with pytest.raises(CorpusRefusal) as caught:
        read_discovery(data_root, RUN_ID)

    assert caught.value.code is RefusalCode.RECORD_INVALID


def test_a_missing_inventory_is_refused(golden: Bodies, data_root: Path) -> None:
    path = _written(golden, data_root)
    path.chmod(0o644)
    path.unlink()

    with pytest.raises(CorpusRefusal) as caught:
        read_discovery(data_root, RUN_ID)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
    assert caught.value.details == {"record": "two.json"}


@pytest.mark.parametrize("run_id", ["absent", "../escape"])
def test_an_unknown_run_is_refused(data_root: Path, run_id: str) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_discovery(data_root, run_id)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
    assert caught.value.message == "no such discovery run"
