"""An unstamped development root must not silently adopt existing evidence."""

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.core.evidence.contract_stamp import STAMP_NAME, require_current_data_root
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from tests.corpus.conftest import last_record
from tests.schema.conftest import KEPT_FRAME_SET


def _evidence(root: Path, name: str = "arbitrary.bin") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(KEPT_FRAME_SET.read_bytes())
    return path


def test_unstamped_evidence_refuses_a_read_and_a_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "data"
    evidence = _evidence(root)
    before = evidence.read_bytes()
    monkeypatch.setenv("DATA_DIR", str(root))
    assert main(["corpus", "inspect-source", "--source-sha256", "0" * 64]) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "RECORD_SCHEMA_UNSUPPORTED"
    assert main(["corpus", "build", "--manifest", str(tmp_path / "absent.yaml")]) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "RECORD_SCHEMA_UNSUPPORTED"
    assert evidence.read_bytes() == before
    assert not (root / STAMP_NAME).exists()


def test_first_write_rechecks_when_evidence_arrives_after_initial_check(tmp_path: Path) -> None:
    from ss_track.core.evidence.contract_stamp import stamp_before_write

    root = tmp_path / "data"
    require_current_data_root(root)
    evidence = _evidence(root)
    with pytest.raises(CorpusRefusal) as caught:
        stamp_before_write(root / "new-record.json")
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert evidence.is_file() and not (root / STAMP_NAME).exists()


def test_fresh_and_operator_inputs_do_not_create_a_stamp(tmp_path: Path) -> None:
    root = tmp_path / "data"
    require_current_data_root(root)
    root.mkdir()
    (root / "declaration.yaml").write_text("schema_version: 1\ncorpus_id: pilot\n")
    (root / "labels.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "labels": [{"kind": "box", "note": "manifest_sha256 and } are text"}],
            }
        )
    )
    require_current_data_root(root)
    assert not (root / STAMP_NAME).exists()


def test_escaped_record_keys_and_symlinked_files_are_detected(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    external = tmp_path / "record"
    source = KEPT_FRAME_SET.read_text()
    assert '"kind"' in source
    external.write_text(source.replace('"kind"', '"ki\\u006ed"', 1))
    (root / "linked").symlink_to(external)
    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(root)
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_scan_a_large_root_of_operator_inputs(
    tmp_path: Path, record_property: Callable[[str, object], None]
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "declaration.yaml").write_text("schema_version: 1\n")
    for folder in range(20):
        directory = root / str(folder)
        directory.mkdir()
        for index in range(500):
            (directory / f"{index}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    started = time.perf_counter()
    require_current_data_root(root)
    elapsed = time.perf_counter() - started
    record_property("unstamped_10000_file_seconds", round(elapsed, 4))
    assert not (root / STAMP_NAME).exists()


def test_nested_record_keys_and_strings_do_not_misclassify_declarations(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    document = {
        "schema_version": 1,
        "text": 'A quote: \\" and braces: { [ ] }',
        "nested": {"kind": "box", "manifest_sha256": "only a nested input field"},
    }
    (root / "operator.json").write_text(json.dumps(document))
    require_current_data_root(root)
    assert not (root / STAMP_NAME).exists()


def test_record_keys_split_across_chunks_are_found(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    document = {
        "filler": "x" * (128 + 65536),
        "kind": "ss-track.example",
        "manifest_sha256": "0" * 64,
    }
    (root / "large-record").write_text(json.dumps(document))
    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(root)
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_directory_symlink_cycle_is_scanned_once(tmp_path: Path) -> None:
    root = tmp_path / "data"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "loop").symlink_to(root, target_is_directory=True)
    (root / "declaration.yaml").write_text("schema_version: 1\n")
    require_current_data_root(root)
    assert not (root / STAMP_NAME).exists()


def test_unreadable_tree_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ss_track.core.evidence import unstamped

    root = tmp_path / "data"
    root.mkdir()

    def fail_walk(path: Path, **kwargs: object) -> object:
        raise PermissionError("cannot inspect")

    monkeypatch.setattr(unstamped.os, "walk", fail_walk)
    with pytest.raises(PermissionError, match="cannot inspect"):
        require_current_data_root(root)
    assert not (root / STAMP_NAME).exists()


@pytest.mark.parametrize(
    "operation",
    ["import", "build", "stage", "verify", "amend", "redecode", "hashes", "compare"],
)
def test_public_corpus_api_refuses_unstamped_root_before_work(
    tmp_path: Path, operation: str
) -> None:
    from ss_track import corpus

    root = tmp_path / "data"
    evidence = _evidence(root)
    source = tmp_path / "absent.yaml"
    actions = {
        "import": lambda: corpus.import_source(source, root),
        "build": lambda: corpus.build_corpus(source, root),
        "stage": lambda: corpus.stage_corpus("sample", root),
        "verify": lambda: corpus.verify_corpus_frames("sample", root),
        "amend": lambda: corpus.amend_source(source, root),
        "redecode": lambda: corpus.redecode_source(source, root),
        "hashes": lambda: corpus.record_staged_hashes("sample", "run", root),
        "compare": lambda: corpus.compare_staged_hashes(source, source, "run", root),
    }
    with pytest.raises(CorpusRefusal) as caught:
        actions[operation]()
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert evidence.exists() and not (root / STAMP_NAME).exists()


def test_non_regular_file_fails_closed_without_blocking(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    os.mkfifo(root / "pipe")
    with pytest.raises(OSError, match="non-regular file"):
        require_current_data_root(root)
    assert not (root / STAMP_NAME).exists()


def test_record_appearing_after_root_check_is_not_read(tmp_path: Path) -> None:
    from ss_track.core.evidence.sealed import read_sealed
    from ss_track.corpus.records.kinds import FRAME_SET

    root = tmp_path / "data"
    require_current_data_root(root)
    evidence = _evidence(root)
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(evidence, FRAME_SET)
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert not (root / STAMP_NAME).exists()


def test_removed_stamp_is_rechecked_before_a_read(tmp_path: Path) -> None:
    from ss_track.core.evidence.contract_stamp import stamp_before_write
    from ss_track.core.evidence.sealed import read_sealed
    from ss_track.corpus.records.kinds import FRAME_SET

    root = tmp_path / "data"
    require_current_data_root(root)
    stamp_before_write(root / "record.json")
    evidence = _evidence(root)
    (root / STAMP_NAME).unlink()
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(evidence, FRAME_SET)
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_new_symlinked_record_is_rechecked_before_read(tmp_path: Path) -> None:
    from ss_track.core.evidence.sealed import read_sealed
    from ss_track.corpus.records.kinds import FRAME_SET

    root = tmp_path / "data"
    root.mkdir()
    require_current_data_root(root)
    external = tmp_path / "record"
    external.write_bytes(KEPT_FRAME_SET.read_bytes())
    path = root / "linked"
    path.symlink_to(external)
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(path, FRAME_SET)
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED


@pytest.mark.parametrize("operation", ["pool", "links", "derive", "freeze", "handoff", "audit"])
def test_other_root_writers_refuse_unstamped_evidence_before_work(
    tmp_path: Path, operation: str
) -> None:
    from ss_track.annotate.derivation.derive import derive_corpus
    from ss_track.corpus.links.portable_accept import accept_handoff
    from ss_track.corpus.links.run import LinkRequest, write_links
    from ss_track.corpus.review.blind import present_audit
    from ss_track.corpus.review.freeze import freeze_corpus
    from ss_track.corpus.sources.pool import prepare_pool

    root = tmp_path / "data"
    evidence = _evidence(root)
    source = tmp_path / "absent.yaml"
    actions = {
        "pool": lambda: prepare_pool(source, "run", root),
        "links": lambda: write_links(LinkRequest("run", "sample"), root),
        "derive": lambda: derive_corpus("sample", source, root),
        "freeze": lambda: freeze_corpus("sample", source, "run", root),
        "handoff": lambda: accept_handoff(root, source, "run", "other", "reviewer", True),
        "audit": lambda: present_audit("audit", ["run"], tmp_path / "output", root),
    }
    with pytest.raises(CorpusRefusal) as caught:
        actions[operation]()
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert evidence.exists() and not (root / STAMP_NAME).exists()


def test_declaration_contracts_cannot_require_record_shape() -> None:
    from ss_track.schema.registry.store import load_contract_set

    contracts = load_contract_set()
    for contract in contracts.contracts:
        if contract.family == "declaration" and contract.versions:
            schema = contracts.frozen_schema(contract, contract.versions[-1])
            assert schema.get("additionalProperties") is False
            assert not {"kind", "manifest_sha256"} <= set(schema.get("properties", {}))


def test_released_stage_reads_unstamped_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ss_track.core.evidence import contract_stamp
    from ss_track.core.evidence.sealed import read_sealed
    from ss_track.corpus.records.kinds import FRAME_SET

    root = tmp_path / "data"
    evidence = _evidence(root)
    monkeypatch.setattr(contract_stamp, "installed_fingerprints", lambda: None)
    require_current_data_root(root)
    assert read_sealed(evidence, FRAME_SET)["kind"] == FRAME_SET.kind
    assert not (root / STAMP_NAME).exists()


def test_clean_can_inspect_unstamped_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    evidence = _evidence(root)
    before = evidence.read_bytes()
    monkeypatch.setenv("DATA_DIR", str(root))
    assert main(["data", "clean", "--kind", "scratch"]) == EXIT_OK
    assert evidence.read_bytes() == before and not (root / STAMP_NAME).exists()


@pytest.mark.parametrize(
    "operation",
    [
        "source",
        "manifest",
        "predecessor",
        "frames",
        "links",
        "discovery",
        "blinding",
        "acquisition",
    ],
)
def test_root_taking_readers_refuse_unstamped_evidence_without_prior_context(
    tmp_path: Path, operation: str
) -> None:
    from ss_track.corpus.bundles.frame_set import read_frame_set
    from ss_track.corpus.discovery.reader import read_discovery
    from ss_track.corpus.links.records import read_links
    from ss_track.corpus.review.blind_key import read_blinding
    from ss_track.corpus.sources.pool_acquisition import load_acquisition
    from ss_track.corpus.sources.stored import load_source_record
    from ss_track.corpus.versions.manifests import load_corpus_manifest, load_predecessor

    root = tmp_path / "data"
    _evidence(root)
    require_current_data_root(tmp_path / "other-root")
    actions = {
        "source": lambda: load_source_record("0" * 64, root),
        "manifest": lambda: load_corpus_manifest("sample", root),
        "predecessor": lambda: load_predecessor("sample", root),
        "frames": lambda: read_frame_set(root, "sample"),
        "links": lambda: read_links(root, "sample"),
        "discovery": lambda: read_discovery(root, "sample"),
        "blinding": lambda: read_blinding(root, "sample"),
        "acquisition": lambda: load_acquisition("sample", root),
    }
    with pytest.raises(CorpusRefusal) as caught:
        actions[operation]()
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_entries_removed_during_the_scan_are_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another command's scratch file or directory can vanish between listing and inspection."""
    from ss_track.core.evidence import unstamped

    root = tmp_path / "data"
    root.mkdir()
    (root / "declaration.yaml").write_text("schema_version: 1\n")
    real_walk = os.walk

    def walk_with_vanished_entries(top: str, **kwargs: object) -> object:
        for directory, folders, files in real_walk(top, **kwargs):  # type: ignore[call-overload]
            if Path(directory) == root:
                folders.append("vanished-scratch")
                files.append("vanished-file.json")
            yield directory, folders, files

    monkeypatch.setattr(unstamped.os, "walk", walk_with_vanished_entries)
    require_current_data_root(root)
    (root / "dangling").symlink_to(tmp_path / "absent")
    require_current_data_root(root)
    assert not (root / STAMP_NAME).exists()


def test_a_vanished_entry_does_not_hide_a_later_record(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "a-dangling").symlink_to(tmp_path / "absent")
    _evidence(root, "z-record")
    with pytest.raises(CorpusRefusal) as caught:
        require_current_data_root(root)
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_checking_another_root_keeps_the_first_root_stamped_and_rechecked(tmp_path: Path) -> None:
    from ss_track.core.evidence.sealed import read_sealed
    from ss_track.core.evidence.sealing import write_sealed
    from ss_track.corpus.records.kinds import FRAME_SET

    first, other = tmp_path / "first", tmp_path / "other"
    require_current_data_root(first)
    require_current_data_root(other)
    record = json.loads(KEPT_FRAME_SET.read_text())
    write_sealed(first / "record.json", record)
    assert (first / STAMP_NAME).is_file()
    assert not (other / STAMP_NAME).exists()

    require_current_data_root(other)
    evidence = _evidence(other / "nested-check")
    with pytest.raises(CorpusRefusal) as caught:
        read_sealed(evidence, FRAME_SET)
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert read_sealed(first / "record.json", FRAME_SET)["kind"] == FRAME_SET.kind
