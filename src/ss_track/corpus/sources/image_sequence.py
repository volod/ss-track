"""Copy, identify and verify the retained bytes of an explicit PNG sequence."""

from pathlib import Path
from typing import Any

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import copy_with_sha256, seal, sha256_file, write_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.core.scratch import READ_ONLY_FILE_MODE
from ss_track.corpus.declarations.image_sequence import ImageSequence
from ss_track.corpus.records.kinds import IMAGE_SEQUENCE

INDEX_NAME = "index.json"


def image_name(index: int) -> str:
    """Return the one retained basename for a declared image index."""
    return f"{index:08d}.png"


def sequence_identity(hashes: list[str]) -> str:
    return sha256_bytes(canonical_json({"kind": "image-sequence", "sha256": [*hashes]}))


def copy_sequence(sequence: ImageSequence, stored: Path) -> tuple[str, int]:
    stored.mkdir()
    hashes: list[str] = []
    size = 0
    for member in sequence.frames:
        target = stored / image_name(member.index)
        if not member.path.is_file():
            raise CorpusRefusal(
                RefusalCode.SOURCE_NOT_FOUND, f"image not found: {member.path.name}"
            )
        found, length = copy_with_sha256(member.path, target)
        if found != member.sha256:
            raise CorpusRefusal(
                RefusalCode.SOURCE_HASH_MISMATCH,
                f"image changed: {member.path.name}",
                {"name": member.path.name, "frame_index": member.index},
            )
        hashes.append(found)
        size += length
        target.chmod(READ_ONLY_FILE_MODE)
    rate = sequence.frame_rate
    write_sealed(
        stored / INDEX_NAME,
        seal(
            {
                **IMAGE_SEQUENCE.stamp(),
                "hashes": [*hashes],
                "frame_rate": None if rate is None else str(rate),
            }
        ),
    )
    (stored / INDEX_NAME).chmod(READ_ONLY_FILE_MODE)
    return sequence_identity(hashes), size


def read_index(stored: Path) -> dict[str, Any]:
    return read_sealed(stored / INDEX_NAME, IMAGE_SEQUENCE)


def verify_sequence(
    stored: Path, identity: str, inventory_hash: str, mismatch: RefusalCode
) -> None:
    """Validate the pinned inventory and every image, including absent members."""
    try:
        if sha256_file(stored / INDEX_NAME) != inventory_hash:
            raise ValueError("sequence inventory changed")
        inventory = read_index(stored)
        hashes = inventory["hashes"]
        if sequence_identity(hashes) != identity:
            raise ValueError("sequence identity changed")
        expected = {INDEX_NAME}
        for index, digest in enumerate(hashes):
            name = image_name(index)
            expected.add(name)
            if sha256_file(stored / name) != digest:
                raise ValueError(f"image changed: {name}")
        if {path.name for path in stored.iterdir()} != expected:
            raise ValueError("sequence membership changed")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CorpusRefusal(mismatch, str(error), {"source_sha256": identity}) from error
