"""The file a recording declaration names: present, readable, and the bytes its hash states.

Import copies it and an amendment hashes it. Both read it the one way here, so a path that is
absent or not a regular file, a file this process may not read, and bytes other than the declared
hash are refused alike by both.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.declaration import RecordingDeclaration
from ss_track.corpus.records.sealing import copy_with_sha256, sha256_file


def require_regular_file(path: Path) -> None:
    """Refuse a declared source that is absent or cannot be read as one file."""
    if not path.exists():
        raise CorpusRefusal(RefusalCode.SOURCE_NOT_FOUND, f"source file not found: {path.name}")
    if not path.is_file():
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, f"not a regular file: {path.name}")


def copy_declared_source(declaration: RecordingDeclaration, stored: Path) -> tuple[str, int]:
    """Copy the declared file and return its hash and size, from the one read that copies it.

    The copy comes first, so the hash and a decode describe exactly the bytes that are retained.
    """
    with _readable():
        sha256, size = copy_with_sha256(declaration.source_path, stored)
    require_declared_hash(declaration.expected_sha256, sha256)
    return sha256, size


def declared_content_hash(declaration: RecordingDeclaration) -> str:
    """Return the file hash, or the declared hash once the original file has gone."""
    declared = declaration.expected_sha256
    path = declaration.source_path
    if declared is not None and not path.exists():
        return declared
    require_regular_file(path)
    with _readable():
        found = sha256_file(path)
    require_declared_hash(declared, found)
    return found


def require_declared_hash(declared: str | None, found: str) -> None:
    """Refuse bytes other than the ones a declared hash names. No declared hash names none."""
    if declared is not None and declared != found:
        raise CorpusRefusal(
            RefusalCode.SOURCE_HASH_MISMATCH,
            "source bytes do not match the declared hash",
            {"expected_sha256": declared, "actual_sha256": found},
        )


@contextmanager
def _readable() -> Iterator[None]:
    """Refuse a file this process may not read as the source's fault, not as storage failing."""
    try:
        yield
    except PermissionError as error:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, str(error.strerror)) from error
