"""What `corpus stage` and `corpus verify` report for one corpus version."""

from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ss_track.core.refusal import JsonValue
from ss_track.corpus.bundles.duplicate_frames import SharedFramesCheck
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.storage.layout import MANIFEST_NAME


@dataclass(frozen=True, slots=True)
class BundleSummary:
    """One stream's bundle as reported to the operator."""

    stream_id: str
    status: str
    transform: str
    bundle_sha256: str
    frame_count: int
    pixel_format: str
    width: int
    height: int
    manifest_path: str
    origin_corpus_id: str | None = None
    origin_stream_id: str | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return this bundle's report, naming a linked version only when frames were reused."""
        record: dict[str, JsonValue] = asdict(self)
        corpus_id = record.pop("origin_corpus_id")
        stream_id = record.pop("origin_stream_id")
        if isinstance(corpus_id, str) and isinstance(stream_id, str):
            record["reused_from"] = {"corpus_id": corpus_id, "stream_id": stream_id}
        return record


@dataclass(frozen=True, slots=True)
class FramesResult:
    """Outcome of staging or verifying every bundle of a corpus version."""

    status: str
    corpus_id: str
    frame_set_sha256: str
    bundles: tuple[BundleSummary, ...]
    shared_frames: SharedFramesCheck

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        record: dict[str, JsonValue] = asdict(self)
        record["bundles"] = [bundle.to_record() for bundle in self.bundles]
        record["shared_frames"] = self.shared_frames.to_record()
        return record


def summarize(
    bundle: FrameBundle, status: str, *, origin: tuple[str, str] | None = None
) -> BundleSummary:
    """State one opened bundle as reported, with the linked version it came from when reused."""
    corpus_id, stream_id = origin if origin is not None else (None, None)
    return BundleSummary(
        stream_id=bundle.stream_id,
        status=status,
        transform=bundle.transform,
        bundle_sha256=bundle.bundle_sha256,
        frame_count=len(bundle),
        pixel_format=bundle.pixel_format,
        width=bundle.width,
        height=bundle.height,
        manifest_path=str(bundle.directory / MANIFEST_NAME),
        origin_corpus_id=corpus_id,
        origin_stream_id=stream_id,
    )


def bundle_hashes(bundles: Iterable[BundleSummary | FrameBundle]) -> dict[str, str]:
    """Return each bundle's hash by stream or case id, which is what a frame set seals."""
    return {bundle.stream_id: bundle.bundle_sha256 for bundle in bundles}
