"""One staged decoded-frame bundle: its layout, `FrameRef` data and verified random access.

Every read and every verification compares bytes with the sealed per-frame hash, so a frame that
changed on disk cannot reach a module, and a failure names the exact frame. Opening a bundle from
its sealed record is `corpus.bundles.bundle_reader`.
"""

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.evidence.sealing import sha256_file
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.storage.layout import MANIFEST_NAME

IDENTITY_TRANSFORM = "identity"
MISSING = "missing"
HASH_MISMATCH = "hash_mismatch"
UNEXPECTED_FILE = "unexpected_file"
MAX_NAMED_FRAMES = 32


def frame_name(frame_index: int, pixel_format: str) -> str:
    """Return a frame's file name, which sorts in presentation order."""
    return f"{frame_index:08d}.{pixel_format}"


def bundle_hash(identity: Mapping[str, JsonValue]) -> str:
    """Hash what makes frames the same frames, so a corpus or stream name cannot change it."""
    return sha256_bytes(canonical_json(identity))


@dataclass(frozen=True, slots=True)
class FrameRef:
    """Identifies one staged frame, and how to reach it, independently of any module."""

    stream_id: str
    source_sha256: str
    frame_index: int
    content_frame_index: int
    pts: int | None
    time_base: str | None
    timestamp_quality: str
    capture_clock_evidence: str | None
    width: int
    height: int
    pixel_format: str
    transform: str
    bundle_sha256: str
    frame_name: str
    sha256: str

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        record: dict[str, JsonValue] = asdict(self)
        return record


@dataclass(frozen=True, slots=True)
class FrameEntry:
    """One line of the frame index."""

    frame_index: int
    content_frame_index: int
    pts: int | None
    sha256: str


@dataclass(frozen=True, slots=True)
class FrameDamage:
    """A file in a bundle that does not match its sealed index."""

    stream_id: str
    frame: str
    reason: str

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        record: dict[str, JsonValue] = asdict(self)
        return record


def damage_details(damage: Sequence[FrameDamage]) -> dict[str, JsonValue]:
    """Count damaged frames and name the first few, bounded for a badly damaged corpus."""
    named: list[JsonValue] = [entry.to_record() for entry in damage[:MAX_NAMED_FRAMES]]
    return {"damaged_count": len(damage), "frames": named}


def frames_corrupted(damage: Sequence[FrameDamage]) -> CorpusRefusal:
    """Build the refusal that names damaged frames of a staged bundle."""
    return CorpusRefusal(
        RefusalCode.FRAME_CORRUPTED,
        f"{len(damage)} staged frame file(s) do not match the sealed index, first "
        f"{damage[0].frame}; remove the bundle and stage it again",
        damage_details(damage),
    )


class FileDigests:
    """Hashes of frame files that have more than one name, each taken once in one command.

    A case frame equal to its parent frame, and a bundle reused from a linked version, are hard
    links to one inode, whose bytes are the same through every name. Hashing that inode once proves
    the bytes of each name, so a check costs the frames that differ, not the names.
    """

    def __init__(self) -> None:
        self._shared: dict[tuple[int, int], str] = {}

    def sha256(self, path: Path) -> str:
        """Return the hash of a file's bytes, hashing a shared inode only the first time."""
        status = path.stat()
        if status.st_nlink < 2:
            return sha256_file(path)
        key = (status.st_dev, status.st_ino)
        found = self._shared.get(key)
        if found is None:
            found = self._shared[key] = sha256_file(path)
        return found


@dataclass(frozen=True, slots=True)
class FrameBundle:
    """A sealed bundle opened for reading."""

    directory: Path
    stream_id: str
    corpus_manifest_sha256: str
    bundle_sha256: str
    source_sha256: str
    pixel_format: str
    width: int
    height: int
    time_base: str | None
    timestamp_quality: str
    capture_clock_evidence: str | None
    selection: range
    entries: tuple[FrameEntry, ...]
    transform: str
    parent_bundle_sha256: str | None

    def __len__(self) -> int:
        return len(self.entries)

    def _entry(self, frame_index: int) -> FrameEntry:
        """Find an entry by index. A generated case can have gaps, so position proves nothing."""
        position = bisect_left(self.entries, frame_index, key=lambda entry: entry.frame_index)
        if position < len(self.entries) and self.entries[position].frame_index == frame_index:
            return self.entries[position]
        raise CorpusRefusal(
            RefusalCode.FRAME_NOT_IN_BUNDLE,
            "frame index is not in this bundle",
            {
                "stream_id": self.stream_id,
                "frame_index": frame_index,
                "start_frame": self.selection.start,
                "end_frame": self.selection.stop,
            },
        )

    def _name(self, entry: FrameEntry) -> str:
        return frame_name(entry.frame_index, self.pixel_format)

    def _ref(self, entry: FrameEntry) -> FrameRef:
        return FrameRef(
            stream_id=self.stream_id,
            source_sha256=self.source_sha256,
            frame_index=entry.frame_index,
            content_frame_index=entry.content_frame_index,
            pts=entry.pts,
            time_base=self.time_base,
            timestamp_quality=self.timestamp_quality,
            capture_clock_evidence=self.capture_clock_evidence,
            width=self.width,
            height=self.height,
            pixel_format=self.pixel_format,
            transform=self.transform,
            bundle_sha256=self.bundle_sha256,
            frame_name=self._name(entry),
            sha256=entry.sha256,
        )

    def frame_ref(self, frame_index: int) -> FrameRef:
        """Return the reference of one frame by its index in the source sequence."""
        return self._ref(self._entry(frame_index))

    def frame_refs(self) -> Iterator[FrameRef]:
        """Return every reference, in presentation order."""
        return map(self._ref, self.entries)

    def read_frame(self, frame_index: int) -> bytes:
        """Return one frame's packed pixels, refusing bytes that do not match the index."""
        entry = self._entry(frame_index)
        name = self._name(entry)
        try:
            pixels = (self.directory / name).read_bytes()
        except FileNotFoundError as error:
            raise frames_corrupted([FrameDamage(self.stream_id, name, MISSING)]) from error
        if sha256_bytes(pixels) != entry.sha256:
            raise frames_corrupted([FrameDamage(self.stream_id, name, HASH_MISMATCH)])
        return pixels

    def damage(self, digests: FileDigests | None = None) -> list[FrameDamage]:
        """Compare every file with the sealed index and name everything that differs.

        `digests` shares the hashes of linked files across the bundles of one command.
        """
        hashed = FileDigests() if digests is None else digests
        found = [
            item
            for entry in self.entries
            if (item := self._entry_damage(entry, hashed)) is not None
        ]
        expected = {self._name(entry) for entry in self.entries} | {MANIFEST_NAME}
        extras = sorted(path.name for path in self.directory.iterdir() if path.name not in expected)
        return found + [FrameDamage(self.stream_id, name, UNEXPECTED_FILE) for name in extras]

    def _entry_damage(self, entry: FrameEntry, digests: FileDigests) -> FrameDamage | None:
        name = self._name(entry)
        try:
            actual = digests.sha256(self.directory / name)
        except FileNotFoundError:
            return FrameDamage(self.stream_id, name, MISSING)
        return None if actual == entry.sha256 else FrameDamage(self.stream_id, name, HASH_MISMATCH)
