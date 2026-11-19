"""Serialize concurrent freezes and publish with an atomic registry replacement.

Every file of the set is written by `write_contract_file`, the shared atomic writer with the mode
of the file it replaces, under the set's directory lock.
"""

import stat
from pathlib import Path

from ss_track.core.scratch import directory_lock, write_atomically
from ss_track.schema.registry.store import REGISTRY_NAME, damaged


def publish(
    root: Path,
    relative: Path,
    payload: bytes,
    registry: bytes,
    original: bytes,
    *,
    replace: bool = False,
) -> None:
    """Lock the directory (no persistent lock file) and reject a stale registry snapshot.

    `replace` is the development stage's in-place re-pin: the file's previous bytes come back if
    the registry cannot be replaced.
    """
    with directory_lock(root):
        if replace:
            _replace_locked(root, relative, payload, registry, original)
        else:
            _publish_locked(root, relative, payload, registry, original)


def _replace_locked(
    root: Path, relative: Path, payload: bytes, registry: bytes, original: bytes
) -> None:
    target = root / relative
    previous = target.read_bytes() if target.is_file() else None
    try:
        write_contract_file(root, target, payload)
        _require_unchanged(root, original)
        write_contract_file(root, root / REGISTRY_NAME, registry)
    except BaseException:
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            write_contract_file(root, target, previous)
        raise


def write_contract_file(root: Path, target: Path, payload: bytes) -> None:
    """Replace one file of the set atomically, keeping its mode, or the registry's for a new one."""
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE((target if target.exists() else root / REGISTRY_NAME).stat().st_mode)
    write_atomically(target, payload, mode=mode)


def _require_unchanged(root: Path, original: bytes) -> None:
    if (root / REGISTRY_NAME).read_bytes() != original:
        raise damaged("registry changed during freeze; retry against the new set")


def _publish_locked(
    root: Path, relative: Path, payload: bytes, registry: bytes, original: bytes
) -> None:
    """Publish the schema before an atomic registry replacement; roll back a failed publication."""
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        # Exclusive create preserves a concurrent author's candidate or frozen file.
        try:
            with target.open("xb") as stream:
                created = True
                stream.write(payload)
        except FileExistsError:
            if target.read_bytes() != payload:
                raise damaged("candidate destination already exists with different bytes") from None
        _require_unchanged(root, original)
        write_contract_file(root, root / REGISTRY_NAME, registry)
    except BaseException:
        if created:
            target.unlink()
        raise
