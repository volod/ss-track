"""Recording what one host staged, with its frames and the facts of the host."""

import json
import platform
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode, open_frame_bundle, record_staged_hashes
from ss_track.corpus.hosts.host_hashes import STAGED_HASHES_NAME, run_directory
from tests.corpus.conftest import WriteCorpus, WriteRecording
from tests.corpus.hosts._host_hashes import CORPUS, RUN, bundle_line, declare_and_stage


@pytest.fixture
def declared(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> tuple[Path, Path]:
    return declare_and_stage(write_recording, write_corpus, data_root)


@pytest.fixture
def left(declared: tuple[Path, Path], data_root: Path) -> Path:
    return record_staged_hashes(CORPUS, RUN, data_root).record_path


def test_a_record_names_every_bundle_frame_and_source_beside_the_host(
    left: Path, data_root: Path
) -> None:
    record = json.loads(left.read_text(encoding="ascii"))
    stream = bundle_line(record, "one")
    ref = open_frame_bundle(data_root / "corpus" / CORPUS / "frames" / "one").frame_ref(2)

    assert left == data_root / "run" / RUN / STAGED_HASHES_NAME
    assert {line["stream_id"] for line in record["bundles"]} == {"one", "one-blur"}
    assert bundle_line(record, "one-blur")["parent_stream_id"] == "one"
    assert stream["frames"][2] == [2, ref.pts, ref.sha256]
    assert ref.pts is not None
    assert record["sources"][0]["codec"] == "mjpeg"
    assert record["sources"][0]["source_pixel_format"] == "yuvj420p"
    assert record["host"] == {
        "machine": platform.machine(),
        "system": platform.system(),
        "python": platform.python_version(),
    }


def test_a_record_states_the_machine_it_ran_on(
    declared: tuple[Path, Path], data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "machine", lambda: "aarch64")

    result = record_staged_hashes(CORPUS, RUN, data_root)

    assert result.host["machine"] == "aarch64"
    assert json.loads(result.record_path.read_text(encoding="ascii"))["host"] == result.host


def test_a_record_states_frames_on_disk_so_damage_writes_none(
    declared: tuple[Path, Path], data_root: Path
) -> None:
    frame = data_root / "corpus" / CORPUS / "frames" / "one" / "00000002.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"corrupted")

    with pytest.raises(CorpusRefusal) as caught:
        record_staged_hashes(CORPUS, RUN, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert not (data_root / "run").exists()


def test_a_corpus_that_never_staged_has_no_record(data_root: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        record_staged_hashes(CORPUS, RUN, data_root)

    assert caught.value.code is RefusalCode.CORPUS_NOT_BUILT


@pytest.mark.parametrize("run_id", ["../escape", "", "Upper"])
def test_a_run_id_that_cannot_name_a_directory_is_refused(data_root: Path, run_id: str) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        run_directory(data_root, run_id)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
