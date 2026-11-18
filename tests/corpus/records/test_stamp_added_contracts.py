"""A stamp that lacks only contracts added since it was written is extended, not refused (17.7).

No record of a contract can be in a root before an install that pins it writes there, so a root
stamped before the contract was added stays usable, and its next sealed write adds the pins. A
changed or removed contract still refuses, and a record of a contract the stamp did not pin when a
command checked the root is served only once the stamp pins it as this install does.
"""

import multiprocessing
from collections.abc import Callable
from multiprocessing.synchronize import Barrier
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_REFUSED
from ss_track.core.evidence import contract_stamp, stamp_file
from ss_track.core.evidence.contract_stamp import (
    installed_fingerprints,
    installed_meanings,
    require_current_data_root,
    stamp_before_write,
)
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.stamp_file import STAMP_NAME, read_stamp, write_stamp
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import FRAME_SET
from tests.corpus.conftest import WriteRecording, last_record
from tests.corpus.records._unstamped import place_record

ADDED = "record/frame-set"  # a contract the root's stamp predates, with a real record kind
ALTERED = "0" * 64


def _pins() -> tuple[dict[str, str], dict[str, str]]:
    structures, meanings = installed_fingerprints(), installed_meanings()
    assert structures is not None and meanings is not None
    return structures, meanings


def _stamp_without(root: Path, *names: str) -> None:
    """Stamp `root` as an install that did not have `names` yet would have stamped it."""
    structures, meanings = _pins()
    root.mkdir(parents=True, exist_ok=True)
    write_stamp(
        root / STAMP_NAME,
        {name: pin for name, pin in structures.items() if name not in names},
        {name: pin for name, pin in meanings.items() if name not in names},
    )


def _refused(action: Callable[[], object]) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        action()
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    return caught.value


def test_a_read_only_command_serves_the_root_and_writes_nothing(
    cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _stamp_without(cli_root, ADDED)
    before = (cli_root / STAMP_NAME).read_bytes()

    assert main(["corpus", "inspect-source", "--source-sha256", "0" * 64]) == EXIT_REFUSED

    assert last_record(caplog)["code"] == "SOURCE_NOT_IMPORTED"
    assert (cli_root / STAMP_NAME).read_bytes() == before


def test_the_first_sealed_write_adds_exactly_the_added_pins(
    clip: Path, write_recording: WriteRecording, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _stamp_without(cli_root, ADDED, "shared/types")
    structures, meanings = _pins()

    assert main(["import", "--source", str(write_recording())]) == 0

    stamped = read_stamp(cli_root / STAMP_NAME)
    assert stamped is not None
    assert (dict(stamped[0]), stamped[1]) == (structures, meanings)


def test_another_pin_for_an_adopted_contract_then_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    _stamp_without(root, ADDED)
    require_current_data_root(root)
    stamp_before_write(root / "record.json")
    structures, _ = _pins()
    monkeypatch.setattr(
        contract_stamp, "installed_fingerprints", lambda: structures | {ADDED: ALTERED}
    )

    refusal = _refused(lambda: require_current_data_root(root))

    assert refusal.details["changed_contracts"] == [ADDED]


@pytest.mark.parametrize("change", ["changed", "removed"])
def test_a_changed_or_removed_contract_still_refuses(tmp_path: Path, change: str) -> None:
    root = tmp_path / "data"
    structures, meanings = _pins()
    name = ADDED if change == "changed" else "record/withdrawn"
    root.mkdir()
    write_stamp(root / STAMP_NAME, structures | {name: ALTERED}, meanings | {name: ALTERED})

    refusal = _refused(lambda: require_current_data_root(root))

    assert refusal.details["changed_contracts"] == [name]


def _extend_as_another_install(root: Path, pin: str) -> Path:
    """Another install pins `ADDED` as `pin`, then writes a record of it, as a writer would."""
    structures, meanings = _pins()
    write_stamp(root / STAMP_NAME, structures | {ADDED: pin}, meanings | {ADDED: pin})
    return place_record(root / "corpus" / "pilot" / "frame-set.json")


def test_a_record_another_install_pinned_otherwise_is_refused_after_the_check(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    _stamp_without(root, ADDED)
    require_current_data_root(root)
    record = _extend_as_another_install(root, ALTERED)

    refusal = _refused(lambda: read_sealed(record, FRAME_SET))

    assert refusal.details["changed_contracts"] == [ADDED]


def test_a_record_another_install_pinned_alike_is_served(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _stamp_without(root, ADDED)
    require_current_data_root(root)
    structures, meanings = _pins()
    write_stamp(root / STAMP_NAME, structures, meanings)  # another install with this one's pins
    record = place_record(root / "corpus" / "pilot" / "frame-set.json")

    assert read_sealed(record, FRAME_SET)["kind"] == FRAME_SET.kind


def test_a_record_of_a_contract_the_stamp_never_pinned_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _stamp_without(root, ADDED)
    record = place_record(root / "corpus" / "pilot" / "frame-set.json")
    require_current_data_root(root)

    refusal = _refused(lambda: read_sealed(record, FRAME_SET))

    assert refusal.details["contract"] == ADDED
    assert refusal.details["record"] == str(record)


def test_a_read_of_a_pinned_contract_does_not_reread_the_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    _stamp_without(root, "record/staged-hashes")
    record = place_record(root / "corpus" / "pilot" / "frame-set.json")
    require_current_data_root(root)
    reads: list[Path] = []
    real = contract_stamp.read_stamp
    monkeypatch.setattr(
        contract_stamp, "read_stamp", lambda path: (reads.append(path), real(path))[1]
    )

    for _ in range(3):
        read_sealed(record, FRAME_SET)

    assert reads == []


def _extend_in_another_process(
    root: str, pin: str, ready: "Barrier", outcome: "multiprocessing.Queue[str]"
) -> None:
    """Check, wait until the other command has checked too, then take the first-write lock."""
    structures, meanings = _pins()
    contract_stamp.installed_fingerprints = lambda: structures | {"record/added": pin}  # type: ignore[assignment]
    contract_stamp.installed_meanings = lambda: meanings | {"record/added": pin}  # type: ignore[assignment]
    try:
        require_current_data_root(Path(root))
        ready.wait(timeout=60)
        stamp_before_write(Path(root) / "record.json")
        outcome.put("extended")
    except CorpusRefusal as refusal:
        outcome.put(str(refusal.code.value))


@pytest.mark.parametrize(
    "pins", [("a" * 64, "a" * 64), ("a" * 64, "b" * 64)], ids=["alike", "other"]
)
def test_concurrent_extensions_leave_one_consistent_stamp(
    tmp_path: Path, pins: tuple[str, str]
) -> None:
    """Both commands pass the unlocked check first, so only the locked recheck can keep one pin."""
    root = tmp_path / "data"
    _stamp_without(root)
    context = multiprocessing.get_context("spawn")
    ready = context.Barrier(2)
    outcome: multiprocessing.Queue[str] = context.Queue()
    workers = [
        context.Process(target=_extend_in_another_process, args=(str(root), pin, ready, outcome))
        for pin in pins
    ]
    for worker in workers:
        worker.start()
    results = sorted(outcome.get(timeout=120) for _ in workers)
    for worker in workers:
        worker.join(timeout=60)

    stamped = stamp_file.read_stamp(root / STAMP_NAME)
    assert stamped is not None
    assert stamped[0]["record/added"] in pins
    if pins[0] == pins[1]:
        assert results == ["extended", "extended"]
    else:
        assert results == ["RECORD_SCHEMA_UNSUPPORTED", "extended"]
