"""Find sealed-looking records in an unstamped root without loading records into memory."""

import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import BinaryIO

from ss_track.core.canonical import SEAL_FIELD
from ss_track.schema.registry.contract import KIND_FIELD

_CHUNK_BYTES = 64 * 1024
_PREFIX_BYTES = 128
_MAX_KEY_BYTES = 128  # Even a fully escaped JSON spelling of either key is shorter.
_KEYS = frozenset({KIND_FIELD, SEAL_FIELD})
_KEY_BYTES = {key.encode("ascii"): key for key in _KEYS}
_WHITESPACE = frozenset(b" \t\r\n")


def is_record_shaped(document: Mapping[str, object]) -> bool:
    """Say whether a loaded JSON object holds both record keys, the shape a walk refuses."""
    return document.keys() >= _KEYS


class _Probe:
    """Find JSON object keys at the top level, ignoring strings and nested objects."""

    def __init__(self) -> None:
        self.depth = 0
        self.in_string = False
        self.escaped = False
        self.word: bytearray | None = None
        self.pending: str | None = None
        self.keys: set[str] = set()
        self.done = False

    def feed(self, chunk: bytes) -> bool:
        for byte in chunk:
            if self.in_string:
                self._string_byte(byte)
            else:
                self._structural_byte(byte)
            if self.keys == _KEYS:
                return True
            if self.done:
                return False
        return False

    def _string_byte(self, byte: int) -> None:
        if self.escaped:
            self._add(byte)
            self.escaped = False
        elif byte == 92:
            self._add(byte)
            self.escaped = True
        elif byte == 34:
            self.in_string = False
            self.pending = _decode_key(self.word)
            self.word = None
        elif byte < 32:
            self.done = True
        else:
            self._add(byte)

    def _add(self, byte: int) -> None:
        if self.word is not None:
            self.word.append(byte)
            if len(self.word) > _MAX_KEY_BYTES:
                self.word = None

    def _structural_byte(self, byte: int) -> None:
        if self.pending is not None and byte not in _WHITESPACE:
            if byte == 58 and self.pending in _KEYS:
                self.keys.add(self.pending)
            self.pending = None
        if byte == 34:
            self.in_string = True
            self.word = bytearray() if self.depth == 1 else None
        elif byte in (123, 91):
            self.depth += 1
        elif byte in (125, 93):
            self.depth -= 1
            if self.depth <= 0:
                self.done = True
        elif byte > 127 or (byte < 32 and byte not in _WHITESPACE):
            self.done = True


def _decode_key(word: bytearray | None) -> str | None:
    if word is None:
        return None
    direct = _KEY_BYTES.get(bytes(word))
    if direct is not None:
        return direct
    if b"\\" not in word:
        return None
    try:
        result: object = json.JSONDecoder().decode('"' + word.decode("utf-8") + '"')
        return result if isinstance(result, str) else None
    except (UnicodeError, ValueError):
        return None


def _object_prefix(stream: BinaryIO) -> bytes:
    """Read through leading whitespace and return the first object chunk, if any."""
    while chunk := stream.read(_PREFIX_BYTES):
        prefix = chunk.lstrip(b" \t\r\n")
        if prefix:
            return prefix if prefix.startswith(b"{") else b""
    return b""


def _record_keys(path: Path) -> bool:
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise OSError(f"cannot inspect non-regular file {path}")
        prefix = _object_prefix(stream)
        if not prefix:
            return False
        probe = _Probe()
        if probe.feed(prefix):
            return True
        while not probe.done and (chunk := stream.read(_CHUNK_BYTES)):
            if probe.feed(chunk):
                return True
    return False


def _is_record(path: Path) -> bool:
    if not stat.S_ISREG(path.stat().st_mode):
        raise OSError(f"cannot inspect non-regular file {path}")
    return _record_keys(path)


def _raise_walk_error(error: OSError) -> None:
    """Fail closed, except for a directory that vanished: it holds no evidence to read."""
    if not isinstance(error, FileNotFoundError):
        raise error


def first_unstamped_record(root: Path) -> Path | None:
    """Return one record-shaped file, following links while avoiding directory cycles.

    An entry that disappears during the walk, such as another command's scratch file, is skipped
    because no read can load it; every other inspection failure raises. Work is linear in
    directory entries and bytes inspected. Memory is bounded by directory
    metadata and a fixed-size input chunk; arbitrary record names and large JSON are supported.
    """
    if not root.exists() and not root.is_symlink():
        return None
    seen: set[tuple[int, int]] = set()
    for directory, folders, files in os.walk(root, followlinks=True, onerror=_raise_walk_error):
        directory_path = Path(directory)
        try:
            info = directory_path.stat()
        except FileNotFoundError:
            folders.clear()
            continue
        identity = (info.st_dev, info.st_ino)
        if identity in seen:
            folders.clear()
            continue
        seen.add(identity)
        folders.sort()
        files.sort()
        for name in files:
            path = directory_path / name
            try:
                if _is_record(path):
                    return path
            except FileNotFoundError:
                continue  # removed during the walk, or a dangling link: no bytes to read
    return None
