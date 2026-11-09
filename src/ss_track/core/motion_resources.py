"""Conservative host CPU and memory limits for optional parallel motion scoring."""

import os
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, RefusalCode

RESERVE_BYTES = 2 * 1024**3
WORKER_BASE_BYTES = 256 * 1024**2
BYTES_PER_PIXEL = 128
_CGROUP_ROOT = Path("/sys/fs/cgroup")
_MEMINFO = Path("/proc/meminfo")
_CGROUP = Path("/proc/self/cgroup")


@dataclass(frozen=True, slots=True)
class HostResources:
    """The effective CPU count and currently available memory, if measurable."""

    cpu_count: int | None
    available_bytes: int | None


def _memory_available(path: Path) -> int:
    for line in path.read_text(encoding="ascii").splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0] == "MemAvailable:" and fields[2] == "kB":
            return int(fields[1]) * 1024
    raise ValueError("available memory is unavailable")


def _cgroup_path(path: Path, root: Path) -> Path:
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("0::"):
            relative = Path(line[3:].lstrip("/"))
            if ".." in relative.parts:
                break
            result = root / relative
            if result.is_dir():
                return result
            break
    raise ValueError("cgroup v2 is unavailable")


def _limits(leaf: Path, root: Path, cpus: int, memory: int) -> tuple[int, int]:
    """Honor every cgroup ancestor that has an active CPU or memory controller."""
    for group in (leaf, *leaf.parents):
        if not group.is_relative_to(root):
            break
        cpus = _cpu_limit(group, cpus)
        memory = _memory_limit(group, memory)
    return cpus, memory


def _cpu_limit(group: Path, cpus: int) -> int:
    value = _optional_text(group / "cpu.max")
    if value is None:
        return cpus
    quota, period = value.split()
    if quota == "max":
        return cpus
    amount, interval = int(quota), int(period)
    if amount <= 0 or interval <= 0:
        raise ValueError("invalid CPU quota")
    return min(cpus, max(1, amount // interval))


def _memory_limit(group: Path, memory: int) -> int:
    value = _optional_text(group / "memory.max")
    if value is None or value.strip() == "max":
        return memory
    current = int((group / "memory.current").read_text(encoding="ascii"))
    limit = int(value)
    if limit < 0 or current < 0:
        raise ValueError("invalid memory limit")
    return min(memory, max(0, limit - current))


def _optional_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="ascii")
    except FileNotFoundError:
        return None


def host_resources() -> HostResources:
    """Read effective Linux resources; unknown values force the serial path."""
    try:
        cpus = len(os.sched_getaffinity(0))
        available = _memory_available(_MEMINFO)
        leaf = _cgroup_path(_CGROUP, _CGROUP_ROOT)
        cpus, available = _limits(leaf, _CGROUP_ROOT, cpus, available)
        return HostResources(cpus, available)
    except (AttributeError, OSError, ValueError, ZeroDivisionError):
        return HostResources(None, None)


def requested_workers(value: str | None) -> int | None:
    """Parse an optional operator cap; absent or auto uses the host-derived cap."""
    if value is None or value == "auto":
        return None
    if not value.isascii() or not value.isdigit() or len(value) > 6 or int(value) < 1:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID, "SST_MOTION_WORKERS must be auto or a positive integer"
        )
    return int(value)


def worker_memory(width: int, height: int) -> int:
    """Reserve space for a worker and several full-resolution intermediate arrays."""
    return WORKER_BASE_BYTES + width * height * BYTES_PER_PIXEL


def restrict_worker_cpus(cpus: tuple[int, ...]) -> None:
    """Limit the worker and any threads started while importing its dependencies."""
    os.sched_setaffinity(0, cpus)
    for task in Path("/proc/self/task").iterdir():
        try:
            os.sched_setaffinity(int(task.name), cpus)
        except ProcessLookupError:
            continue


def choose_workers(
    host: HostResources, streams: int, requested: int | None, per_worker: int
) -> int:
    """Choose at most half the effective CPUs and the workers that fit after reserve."""
    if host.cpu_count is None or host.available_bytes is None or per_worker <= 0:
        return 1
    cpu_limit = max(1, host.cpu_count // 2)
    memory_limit = max(1, (host.available_bytes - RESERVE_BYTES) // per_worker)
    return max(1, min(streams, requested or cpu_limit, cpu_limit, memory_limit))
