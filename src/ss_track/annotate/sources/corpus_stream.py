"""One corpus stream as a freeze addresses it: its stored source and where its labels live.

A frozen revision sits at ``$DATA_DIR/corpus/<corpus-id>/labels/<stream-id>/``. Naming the
stream instead of three paths reads the source import stored for it and writes there, so the
labels cannot be frozen against one source and filed under another.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.decoding.streams import recorded_video_stream_index
from ss_track.corpus.sources.stored import load_verified_source
from ss_track.corpus.storage.layout import label_document_path, label_revision_path
from ss_track.corpus.versions.manifests import load_corpus_manifest


@dataclass(frozen=True, slots=True)
class StreamTarget:
    """The stored source of one stream and the two files its frozen revision is written to."""

    stream: Mapping[str, JsonValue]
    source: Path
    video_stream_index: int | None
    labels_out: Path
    revision_out: Path


def stream_target(corpus_id: str, stream_id: str, data_root: Path) -> StreamTarget:
    """Return where one stream's source is stored and where its frozen labels belong.

    The stored bytes are hashed again. A generated case is refused, because its labels are
    derived and never frozen by hand.
    """
    manifest = load_corpus_manifest(corpus_id, data_root)
    stream = _named(manifest, "streams", "stream_id", stream_id)
    if stream is None:
        if _named(manifest, "generated_cases", "case_id", stream_id) is not None:
            raise invalid(f"{stream_id} is a generated case; its labels are derived, not frozen")
        raise invalid(f"corpus {corpus_id} has no stream {stream_id}")
    source = load_verified_source(str(stream["source_sha256"]), data_root)
    index = None if source.stored.is_dir() else recorded_video_stream_index(source.sequence)
    return StreamTarget(
        stream,
        source.stored,
        index,
        label_document_path(data_root, corpus_id, stream_id),
        label_revision_path(data_root, corpus_id, stream_id),
    )


def _named(
    manifest: Mapping[str, JsonValue], listed: str, key: str, wanted: str
) -> Mapping[str, JsonValue] | None:
    entries = manifest.get(listed)
    if not isinstance(entries, list):
        raise TypeError(f"{listed} is not a list")
    for entry in entries:
        if isinstance(entry, dict) and entry.get(key) == wanted:
            return entry
    return None
