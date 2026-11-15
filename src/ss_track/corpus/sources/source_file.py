"""The file or image sequence a recording declaration names: readable, and the bytes it states.

Import copies it and an amendment hashes it. Both read it the one way here, so a path that is
absent or not a regular file, a file this process may not read, and bytes other than the declared
hash are refused alike by both.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ss_track.core.evidence.sealing import copy_with_sha256, sha256_file
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.declaration import RecordingDeclaration
from ss_track.corpus.sources.image_sequence import copy_sequence, sequence_identity


def require_regular_file(path: Path) -> None:
    """Refuse a declared source that is absent or cannot be read as one file."""
    if not path.exists():
        raise CorpusRefusal(RefusalCode.SOURCE_NOT_FOUND, f"source file not found: {path.name}")
    if not path.is_file():
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, f"not a regular file: {path.name}")


def copy_declared_source(declaration: RecordingDeclaration, stored: Path) -> tuple[str, int]:
    """Copy the declared file or image sequence and return its content hash and size.

    The hash comes from the one read that copies the bytes, so the hash and a decode describe
    exactly the bytes that are retained. A sequence's content hash is its source identity.
    """
    images = declaration.image_sequence
    with _readable():
        if images is None:
            sha256, size = copy_with_sha256(declaration.source_path, stored)
        else:
            sha256, size = copy_sequence(images, stored)
    require_declared_hash(declaration.expected_sha256, sha256)
    return sha256, size


def declared_content_hash(declaration: RecordingDeclaration) -> str:
    """Return the content hash, or the declared hash once the original has gone.

    Every image of a sequence declares its hash, so an image already removed counts by it, and
    one still present must still match it.
    """
    declared = declaration.expected_sha256
    path = declaration.source_path
    if declared is not None and not path.exists():
        return declared
    images = declaration.image_sequence
    if images is None:
        found = _file_hash(path)
    else:
        found = sequence_identity(
            [
                _file_hash(member.path, member.sha256) if member.path.exists() else member.sha256
                for member in images.frames
            ]
        )
    require_declared_hash(declared, found)
    return found


def _file_hash(path: Path, declared: str | None = None) -> str:
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
