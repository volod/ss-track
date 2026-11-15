"""Store one staged frame, linking a parent frame when the bytes are the same.

A generated case calls this with its parent frame. Stream staging calls it without a parent, so
every decoded frame is a new file. Reading a bundle never looks at the link: it hashes the bytes.
"""

import errno
import os
import shutil
from pathlib import Path

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import READ_ONLY_FILE_MODE
from ss_track.corpus.bundles.frames import frame_name
from ss_track.corpus.decoding.pixels import OUTPUT_PIXEL_FORMAT, frame_size_bytes

# Linux reports a cross-device link as EXDEV and a filesystem without hard links as EPERM or
# ENOTSUP. EMLINK means this inode cannot take another name, so a copy still stores the frame.
_COPY_INSTEAD = frozenset({errno.EXDEV, errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EMLINK})


def store_frame(
    directory: Path,
    frame_index: int,
    pts: int | None,
    pixels: bytes,
    *,
    link_from: Path | None = None,
    link_sha256: str | None = None,
) -> dict[str, JsonValue]:
    """Write one read-only frame and return its line of the sealed index.

    `link_from` is a parent frame whose sealed hash is `link_sha256`. When `pixels` has that
    hash, the new name is a hard link to the parent, so those bytes take no extra disk. A
    filesystem that cannot link the two directories stores a copy. The index hash is the hash
    of `pixels` either way.
    """
    path = directory / frame_name(frame_index, OUTPUT_PIXEL_FORMAT)
    digest = sha256_bytes(pixels)
    if not _linked(path, link_from, digest, link_sha256, len(pixels)):
        path.write_bytes(pixels)
    path.chmod(READ_ONLY_FILE_MODE)
    return {"frame_index": frame_index, "pts": pts, "sha256": digest}


def require_space(root: Path, frames: int, width: int, height: int) -> None:
    """Refuse before work that could not finish. Raw frames dwarf their source."""
    required = frames * frame_size_bytes(width, height)
    free = shutil.disk_usage(root).free
    if free < required:
        raise CorpusRefusal(
            RefusalCode.STORAGE_FAILED,
            "not enough free space to stage these frames",
            {"required_bytes": required, "free_bytes": free},
        )


def linked_name(source: Path, target: Path) -> bool:
    """Hard-link `source` as `target`. False when this filesystem cannot link the two names."""
    try:
        os.link(source, target)
    except OSError as error:
        if error.errno not in _COPY_INSTEAD:
            raise
        return False
    return True


def _linked(
    path: Path, source: Path | None, digest: str, link_sha256: str | None, size: int
) -> bool:
    """Link `source` onto `path` when it is this frame. False means the caller copies."""
    if source is None or link_sha256 != digest or source.stat().st_size != size:
        return False
    return linked_name(source, path)
