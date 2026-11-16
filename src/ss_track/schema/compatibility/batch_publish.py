"""Publish a validated batch of development files under the contract-set lock."""

import fcntl
import os
from pathlib import Path

from ss_track.schema.compatibility.publishing import _write_atomically
from ss_track.schema.registry.store import REGISTRY_NAME, damaged


def publish_batch(
    root: Path,
    changes: dict[Path, bytes],
    previous: dict[Path, bytes | None],
    registry: bytes,
    original: bytes,
) -> None:
    """Refuse stale inputs and roll back replaced files when publication fails."""
    descriptor = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if (root / REGISTRY_NAME).read_bytes() != original:
            raise damaged("registry changed during generation; retry against the new set")
        for relative, old in previous.items():
            target = root / relative
            current = target.read_bytes() if target.is_file() else None
            if current != old:
                raise damaged(f"{relative} changed during generation; retry against the new set")
        written: list[Path] = []
        try:
            for relative, payload in changes.items():
                _write_atomically(root, root / relative, payload)
                written.append(relative)
            if registry != original:
                _write_atomically(root, root / REGISTRY_NAME, registry)
        except BaseException:
            for relative in reversed(written):
                target = root / relative
                old = previous[relative]
                if old is None:
                    target.unlink(missing_ok=True)
                else:
                    _write_atomically(root, target, old)
            raise
    finally:
        os.close(descriptor)
