"""One staged decoded-frame bundle: its layout, `FrameRef` data and verified random access.

Every read and every verification compares bytes with the sealed per-frame hash, so a frame that
changed on disk cannot reach a module, and a failure names the exact frame.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ss_track.corpus.builder import CORPUS_DIRECTORY
from ss_track.corpus.importer import MANIFEST_NAME
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import (
    canonical_json,
    read_sealed,
    require_schema,
    sha256_bytes,
    sha256_file,
)

FRAME_BUNDLE_KIND = "ss-track.frame-bundle"
BUNDLE_SCHEMA_VERSION = 2
FRAMES_DIRECTORY = "frames"
IDENTITY_TRANSFORM = "identity"
MISSING = "missing"
HASH_MISMATCH = "hash_mismatch"
UNEXPECTED_FILE = "unexpected_file"
_MAX_NAMED_FRAMES = 32


def frames_root(data_root: Path, corpus_id: str) -> Path:
    """Return the directory that holds every bundle of one corpus version."""
    return data_root / CORPUS_DIRECTORY / corpus_id / FRAMES_DIRECTORY


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


def frames_corrupted(damage: Sequence[FrameDamage]) -> CorpusRefusal:
    """Build the refusal that names damaged frames, bounded for a badly damaged corpus."""
    named: list[JsonValue] = [entry.to_record() for entry in damage[:_MAX_NAMED_FRAMES]]
    return CorpusRefusal(
        RefusalCode.FRAME_CORRUPTED,
        f"{len(damage)} staged frame file(s) do not match the sealed index, first "
        f"{damage[0].frame}; remove the bundle and stage it again",
        {"damaged_count": len(damage), "frames": named},
    )


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
    start_frame: int
    entries: tuple[FrameEntry, ...]

    def __len__(self) -> int:
        return len(self.entries)

    def _entry(self, frame_index: int) -> FrameEntry:
        position = frame_index - self.start_frame
        if not 0 <= position < len(self.entries):
            raise CorpusRefusal(
                RefusalCode.FRAME_NOT_IN_BUNDLE,
                "frame index is outside this bundle",
                {
                    "stream_id": self.stream_id,
                    "frame_index": frame_index,
                    "start_frame": self.start_frame,
                    "end_frame": self.start_frame + len(self.entries),
                },
            )
        return self.entries[position]

    def _name(self, entry: FrameEntry) -> str:
        return frame_name(entry.frame_index, self.pixel_format)

    def _ref(self, entry: FrameEntry) -> FrameRef:
        return FrameRef(
            stream_id=self.stream_id,
            source_sha256=self.source_sha256,
            frame_index=entry.frame_index,
            pts=entry.pts,
            time_base=self.time_base,
            timestamp_quality=self.timestamp_quality,
            capture_clock_evidence=self.capture_clock_evidence,
            width=self.width,
            height=self.height,
            pixel_format=self.pixel_format,
            transform=IDENTITY_TRANSFORM,
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

    def damage(self) -> list[FrameDamage]:
        """Compare every file with the sealed index and name everything that differs."""
        found = [item for entry in self.entries if (item := self._entry_damage(entry)) is not None]
        expected = {self._name(entry) for entry in self.entries} | {MANIFEST_NAME}
        extras = sorted(path.name for path in self.directory.iterdir() if path.name not in expected)
        return found + [FrameDamage(self.stream_id, name, UNEXPECTED_FILE) for name in extras]

    def _entry_damage(self, entry: FrameEntry) -> FrameDamage | None:
        name = self._name(entry)
        try:
            actual = sha256_file(self.directory / name)
        except FileNotFoundError:
            return FrameDamage(self.stream_id, name, MISSING)
        return None if actual == entry.sha256 else FrameDamage(self.stream_id, name, HASH_MISMATCH)


def open_frame_bundle(directory: Path) -> FrameBundle:
    """Open a bundle directory, refusing one whose record is not intact."""
    manifest = read_sealed(directory / MANIFEST_NAME, FRAME_BUNDLE_KIND)
    require_schema(manifest, BUNDLE_SCHEMA_VERSION, directory / MANIFEST_NAME)
    try:
        bundle = _parse_bundle(directory, manifest)
    except (KeyError, TypeError) as error:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "bundle record is incomplete",
            {"record": MANIFEST_NAME, "field": str(error)},
        ) from error
    if bundle_hash(_identity(manifest)) != bundle.bundle_sha256:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "bundle hash does not cover this frame index",
            {"record": MANIFEST_NAME},
        )
    return bundle


def _identity(manifest: Mapping[str, Any]) -> dict[str, JsonValue]:
    identity: dict[str, JsonValue] = manifest["identity"]
    return identity


def _parse_bundle(directory: Path, manifest: Mapping[str, Any]) -> FrameBundle:
    identity: Mapping[str, Any] = _identity(manifest)
    return FrameBundle(
        directory=directory,
        stream_id=manifest["stream_id"],
        corpus_manifest_sha256=manifest["corpus_manifest_sha256"],
        bundle_sha256=manifest["bundle_sha256"],
        source_sha256=identity["source_sha256"],
        pixel_format=identity["pixel_format"],
        width=identity["width"],
        height=identity["height"],
        time_base=identity["time_base"],
        timestamp_quality=manifest["timestamp_quality"],
        capture_clock_evidence=manifest["capture_clock_evidence"],
        start_frame=identity["selection"]["start_frame"],
        entries=tuple(
            FrameEntry(entry["frame_index"], entry["pts"], entry["sha256"])
            for entry in identity["frames"]
        ),
    )
