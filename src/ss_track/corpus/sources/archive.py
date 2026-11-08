"""Bounded extraction of explicitly selected files from an untrusted ZIP archive."""

import hashlib
import os
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from ss_track.core.refusal import CorpusRefusal, RefusalCode

_CHUNK_BYTES = 1024 * 1024


def _invalid(message: str) -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.SOURCE_DAMAGED, message)


def _safe_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    path = PurePosixPath(name.rstrip("/"))
    if (
        not name
        or not name.isascii()
        or "\\" in name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
        or ":" in path.parts[0]
        or str(path) != name.rstrip("/")
    ):
        raise _invalid("archive contains an unsafe path")
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise _invalid("archive contains a non-regular entry")
    if info.flag_bits & 1:
        raise _invalid("archive contains an encrypted entry")
    return name.rstrip("/")


def _entries(archive: zipfile.ZipFile, selection: set[str], budget: int) -> list[zipfile.ZipInfo]:
    if budget < 0 or not selection:
        raise _invalid("archive selection and nonnegative budget are required")
    seen: set[str] = set()
    selected: list[zipfile.ZipInfo] = []
    for info in archive.infolist():
        name = _safe_name(info)
        if name in seen:
            raise _invalid("archive contains duplicate paths")
        seen.add(name)
        if name in selection and not info.is_dir():
            selected.append(info)
    if {entry.filename for entry in selected} != selection:
        raise _invalid("archive selection is incomplete or missing")
    if sum(entry.file_size for entry in selected) > budget:
        raise _invalid("archive selection exceeds extraction budget")
    return sorted(selected, key=lambda entry: entry.filename)


def _target(root: Path, name: str) -> Path:
    target = root.joinpath(*PurePosixPath(name).parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise _invalid("archive destination escapes its root")
    for parent in (target, *target.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise _invalid("archive destination contains a symbolic link")
    return target


def _copy(archive: zipfile.ZipFile, info: zipfile.ZipInfo, root: Path) -> tuple[str, str]:
    target = _target(root, info.filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    fd, temporary = tempfile.mkstemp(prefix=".extract-", dir=target.parent)
    scratch = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as out, archive.open(info) as source:
            count = 0
            while chunk := source.read(_CHUNK_BYTES):
                count += len(chunk)
                if count > info.file_size:
                    raise _invalid("archive entry exceeds its declared size")
                digest.update(chunk)
                out.write(chunk)
            if count != info.file_size:
                raise _invalid("archive entry has an incomplete size")
        if target.exists():
            with target.open("rb") as current:
                existing = hashlib.file_digest(current, "sha256").hexdigest()
            if existing != digest.hexdigest():
                raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "archive destination conflicts")
        else:
            try:
                os.link(scratch, target)
            except FileExistsError as error:
                raise CorpusRefusal(
                    RefusalCode.IMPORT_CONFLICT, "archive destination conflicts"
                ) from error
        return info.filename, digest.hexdigest()
    finally:
        scratch.unlink(missing_ok=True)


def extract_selected(
    archive_path: Path, root: Path, selection: set[str], budget: int
) -> dict[str, str]:
    """Extract chosen regular files, refusing unsafe archives and existing conflicting bytes.

    Budget is the sum of declared uncompressed selected bytes. A retry reuses identical files.
    The caller verifies the archive's upstream checksum before invoking this helper.
    """
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = _entries(archive, selection, budget)
            return dict(_copy(archive, entry, root) for entry in entries)
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError) as error:
        raise _invalid("archive could not be safely extracted") from error
