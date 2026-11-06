"""Source identity for one video stream of one file.

The first video stream keeps the file hash, so a one-stream import keeps the source hash and the
manifest bytes it had before a file could hold two cameras. A later stream hashes that file hash
with its index. A one-stream import never produces that form. The file hash remains the recording:
two source identities of one file are still one recording for grouping and lineage.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.decoding.streams import recorded_video_stream_index
from ss_track.corpus.records.sealing import sha256_file

CONTENT_SHA256 = "content_sha256"
_IDENTITY_KIND = "video-stream"
_BYTE_MISMATCH = {
    RefusalCode.RECORD_TAMPERED: "the stored source no longer matches its hash",
    RefusalCode.SOURCE_HASH_MISMATCH: "stored source bytes do not match the imported hash",
}


def source_identity(content_sha256: str, video_stream_index: int) -> str:
    """Return the identity a corpus uses to name this video stream of this file.

    Index 0 returns `content_sha256` unchanged. A later index returns the SHA-256 of the canonical
    JSON object `{"content_sha256", "kind": "video-stream", "video_stream_index"}`.
    """
    if video_stream_index == 0:
        return content_sha256
    payload: dict[str, JsonValue] = {
        "content_sha256": content_sha256,
        "kind": _IDENTITY_KIND,
        "video_stream_index": video_stream_index,
    }
    return sha256_bytes(canonical_json(payload))


def addressed_identity(content_sha256: str, video_stream_index: int | None) -> str:
    """Return the identity a declaration addresses. An omitted index names the first stream."""
    return source_identity(content_sha256, 0 if video_stream_index is None else video_stream_index)


def recording_sha256(stream: Mapping[str, Any]) -> str:
    """Return the file hash this stream shares with the other camera of its container.

    A source whose identity is already the file hash stores no separate field.
    """
    content = stream.get(CONTENT_SHA256)
    if isinstance(content, str):
        return content
    return str(stream["source_sha256"])


def _stated_content(manifest: Mapping[str, Any]) -> str | None:
    source = manifest.get("source")
    value = source.get("sha256") if isinstance(source, Mapping) else None
    if isinstance(value, str):
        return value
    return None


def recorded_content_sha256(manifest: Mapping[str, Any]) -> str:
    """Return the file hash a source record stores, refusing a record that has none."""
    value = _stated_content(manifest)
    if value is None:
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "source record has no content hash")
    return value


def _stated_index(manifest: Mapping[str, Any]) -> int:
    sequence = manifest.get("sequence", {})
    if not isinstance(sequence, Mapping):
        return 0
    return recorded_video_stream_index(sequence)


def _stored_name(manifest: Mapping[str, Any]) -> str:
    source = manifest.get("source")
    name = source.get("stored_name") if isinstance(source, Mapping) else None
    if not isinstance(name, str):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "source record has no stored file name")
    return name


def require_stored_source(
    directory: Path, manifest: Mapping[str, Any], *, mismatch: RefusalCode
) -> Path:
    """Return the stored file when its bytes belong in this directory.

    A current record names the file hash, and the directory is the source identity. A record from
    before a later stream had its own identity can state a different hash; its directory is still
    the file hash, which is what a redecode reads. `mismatch` is the refusal when the bytes are
    not the ones the directory or the record names.
    """
    stored = directory / _stored_name(manifest)
    identity = directory.name
    if not stored.is_file():
        raise CorpusRefusal(mismatch, _BYTE_MISMATCH[mismatch], {"source_sha256": identity})
    file_hash = sha256_file(stored)
    content = _stated_content(manifest)
    index = _stated_index(manifest)
    if content == file_hash and identity == source_identity(file_hash, index):
        return stored
    if index == 0 and identity == file_hash:
        return stored
    raise CorpusRefusal(mismatch, _BYTE_MISMATCH[mismatch], {"source_sha256": identity})
