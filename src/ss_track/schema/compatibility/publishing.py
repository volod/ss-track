"""Serialize concurrent freezes and publish with an atomic registry replacement."""

import fcntl
import os
import stat
import tempfile
from pathlib import Path

from ss_track.schema.registry.store import REGISTRY_NAME, damaged


def publish(root: Path, relative: Path, payload: bytes, registry: bytes, original: bytes) -> None:
    """Lock the directory (no persistent lock file) and reject a stale registry snapshot."""
    descriptor = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _publish_locked(root, relative, payload, registry, original)
    finally:
        os.close(descriptor)


def _publish_locked(
    root: Path, relative: Path, payload: bytes, registry: bytes, original: bytes
) -> None:
    """Publish the schema before an atomic registry replacement; roll back a failed publication."""
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    registry_path = root / REGISTRY_NAME
    created = False
    temporary: Path | None = None
    try:
        # Exclusive create preserves a concurrent author's candidate or frozen file.
        try:
            with target.open("xb") as stream:
                created = True
                stream.write(payload)
        except FileExistsError:
            if target.read_bytes() != payload:
                raise damaged("candidate destination already exists with different bytes") from None
        with tempfile.NamedTemporaryFile(dir=root, prefix=".registry-", delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), stat.S_IMODE(registry_path.stat().st_mode))
            stream.write(registry)
        if registry_path.read_bytes() != original:
            raise damaged("registry changed during freeze; retry against the new set")
        os.replace(temporary, registry_path)
    except BaseException:
        if created:
            target.unlink()
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
