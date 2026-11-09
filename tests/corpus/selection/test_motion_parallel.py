"""Parallel motion keeps exact scores and respects host resource limits."""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from ss_track.core import motion_resources
from ss_track.core.motion_resources import (
    HostResources,
    choose_workers,
    requested_workers,
)
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.selection import motion


@dataclass(frozen=True)
class _Ref:
    frame_index: int
    width: int = 4
    height: int = 4


@dataclass(frozen=True)
class _Bundle:
    stream_id: str
    width: int = 4
    height: int = 4
    damaged: bool = False

    def frame_refs(self) -> list[_Ref]:
        return [_Ref(0), _Ref(1), _Ref(2)]

    def read_frame(self, frame_index: int) -> bytes:
        if self.damaged and frame_index == 1:
            raise CorpusRefusal(RefusalCode.FRAME_CORRUPTED, "damaged frame", {"frame": "1"})
        return bytes([frame_index * 20] * (self.width * self.height * 3))


def test_worker_budget_respects_cpu_memory_and_operator_limit() -> None:
    host = HostResources(cpu_count=12, available_bytes=8 * 1024**3)
    assert choose_workers(host, 20, 1, 10) == 1
    assert choose_workers(host, 20, 20, 10) == 6
    assert choose_workers(host, 20, 20, 2 * 1024**3) == 3
    assert choose_workers(HostResources(None, 8 * 1024**3), 20, 20, 10) == 1
    assert choose_workers(HostResources(12, None), 20, 20, 10) == 1


def test_scheduler_stops_adding_work_when_headroom_falls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(motion, "host_resources", lambda: HostResources(12, 2 * 1024**3))
    assert motion._capacity(6, None, 3, 1024**3) == 3
    assert motion._capacity(6, None, 0, 1024**3) == 1
    monkeypatch.setattr(motion, "host_resources", lambda: HostResources(None, None))
    assert motion._capacity(6, None, 3, 1024**3) == 1


def test_insufficient_memory_refuses_before_reading_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(motion, "host_resources", lambda: HostResources(12, 1))
    with pytest.raises(CorpusRefusal) as caught:
        motion.stream_changes([_Bundle("a"), _Bundle("b")])  # type: ignore[arg-type]
    assert caught.value.code == RefusalCode.WORKER_FAILED
    assert caught.value.details["available_bytes"] == 1


@pytest.mark.skipif(not hasattr(os, "sched_setaffinity"), reason="Linux CPU affinity required")
def test_worker_affinity_includes_threads_started_by_numpy() -> None:
    script = """
import os
from pathlib import Path
import numpy
from ss_track.core.motion_resources import restrict_worker_cpus
numpy.ones((4, 4)) @ numpy.ones((4, 4))
chosen = tuple(sorted(os.sched_getaffinity(0))[:1])
restrict_worker_cpus(chosen)
for task in Path('/proc/self/task').iterdir():
    assert os.sched_getaffinity(int(task.name)) == set(chosen)
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_cgroup_parent_limits_are_applied_and_missing_resources_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cgroup"
    leaf = root / "parent" / "leaf"
    leaf.mkdir(parents=True)
    (root / "parent" / "cpu.max").write_text("300000 100000")
    (root / "parent" / "memory.max").write_text(str(8 * 1024**3))
    (root / "parent" / "memory.current").write_text(str(5 * 1024**3))
    cgroup = tmp_path / "proc-cgroup"
    cgroup.write_text("0::/parent/leaf\n")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(f"MemAvailable: {9 * 1024**2} kB\n")
    monkeypatch.setattr(motion_resources, "_CGROUP_ROOT", root)
    monkeypatch.setattr(motion_resources, "_CGROUP", cgroup)
    monkeypatch.setattr(motion_resources, "_MEMINFO", meminfo)
    monkeypatch.setattr(motion_resources.os, "sched_getaffinity", lambda pid: set(range(12)))
    assert motion_resources.host_resources() == HostResources(3, 3 * 1024**3)
    assert choose_workers(motion_resources.host_resources(), 10, None, 1024**3) == 1
    meminfo.write_text("MemFree: 5 kB\n")
    assert motion_resources.host_resources() == HostResources(None, None)


@pytest.mark.parametrize("value", ["0", "-1", "2.5", "", " AUTO", "9" * 5000])
def test_invalid_worker_configuration_is_refused(value: str) -> None:
    with pytest.raises(CorpusRefusal):
        requested_workers(value)


def test_parallel_scores_and_corruption_match_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SST_MOTION_WORKERS", "2")
    monkeypatch.setattr(motion, "host_resources", lambda: HostResources(4, 8 * 1024**3))
    bundles = [_Bundle("a"), _Bundle("b")]
    parallel = motion.stream_changes(bundles)  # type: ignore[arg-type]
    assert parallel == {"a": {1: 20.0, 2: 20.0}, "b": {1: 20.0, 2: 20.0}}
    monkeypatch.setenv("SST_MOTION_WORKERS", "1")
    assert motion.stream_changes(bundles) == parallel  # type: ignore[arg-type]
    monkeypatch.setenv("SST_MOTION_WORKERS", "2")
    with pytest.raises(CorpusRefusal) as caught:
        motion.stream_changes([_Bundle("a", damaged=True), _Bundle("b")])  # type: ignore[arg-type]
    assert caught.value.code == RefusalCode.FRAME_CORRUPTED
    assert caught.value.details == {"frame": "1"}
