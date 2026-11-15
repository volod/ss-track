"""Copy, identify and verify the retained bytes of an explicit PNG sequence.

Import keeps a sequence as one directory: each image under its index's name and a sealed
`index.json` inventory of the ordered image hashes and the declared rate. The source record pins
the inventory's bytes, so membership and timing cannot change unseen.
"""

from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import copy_with_sha256, seal, sha256_file, write_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import READ_ONLY_FILE_MODE
from ss_track.corpus.declarations.image_sequence import ImageSequence
from ss_track.corpus.records.kinds import IMAGE_SEQUENCE

INDEX_NAME = "index.json"
IMAGE_NAME_PATTERN = "%08d.png"  # the retained names in FFmpeg's image2 notation
_IDENTITY_KIND = "image-sequence"


def image_name(index: int) -> str:
    """Return the one retained basename for a declared image index."""
    return IMAGE_NAME_PATTERN % index


def sequence_identity(hashes: list[str]) -> str:
    """Return the source identity of these ordered image hashes, under the sequence domain tag."""
    return sha256_bytes(canonical_json({"kind": _IDENTITY_KIND, "sha256": [*hashes]}))


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
    """Read the sealed inventory of a retained sequence."""
    return read_sealed(stored / INDEX_NAME, IMAGE_SEQUENCE)


def inventory_pin(stored: Path) -> dict[str, JsonValue]:
    """Return the source-record field that pins a retained sequence's inventory bytes."""
    return {"inventory_sha256": sha256_file(stored / INDEX_NAME)}


def retained_images(stored: Path, inventory: Mapping[str, Any]) -> list[Path]:
    """Return the retained images in their declared order."""
    return [stored / image_name(index) for index in range(len(inventory["hashes"]))]


def declared_rate(inventory: Mapping[str, Any]) -> Fraction | None:
    """Return the frame rate the inventory states, or None when the declaration gave none."""
    rate = inventory["frame_rate"]
    return None if rate is None else Fraction(rate)


def match_retained_images(stored: Path, hashes: list[str]) -> None:
    """Raise ValueError when a retained image is missing, differs, or another name is present.

    Callers choose the refusal code. A missing image is named by its retained basename, not by a
    machine path.
    """
    expected = {INDEX_NAME}
    for index, digest in enumerate(hashes):
        name = image_name(index)
        expected.add(name)
        path = stored / name
        if not path.is_file():
            raise ValueError(f"image not found: {name}")
        if sha256_file(path) != digest:
            raise ValueError(f"image changed: {name}")
    if {path.name for path in stored.iterdir()} != expected:
        raise ValueError("sequence membership changed")


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
        match_retained_images(stored, hashes)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CorpusRefusal(mismatch, str(error), {"source_sha256": identity}) from error
