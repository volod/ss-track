"""The per-frame rows of a descriptor's `frames` table, from a full or a projected bundle record.

A public descriptor passes a record that its contract projected, so a fact not marked public is
absent from the record and therefore from the row. A full record yields every fact. One function
serves both, so the two tables cannot drift apart.
"""

from collections.abc import Iterator, Mapping
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.bundles.bundle_reader import content_frame_index
from ss_track.corpus.bundles.frames import frame_name
from ss_track.corpus.storage.layout import FRAMES_DIRECTORY

STREAM_KEY = "stream_id"
LAYOUT_KEYS = ("width", "height", "pixel_format", "bytes_per_frame", "time_base")
_ENTRY_KEYS = ("pts", "sha256")
_PATH_KEYS = frozenset({STREAM_KEY, "frame_index", "pixel_format"})
_FRAMES_FROM_DESCRIPTOR = f"../../{FRAMES_DIRECTORY}"  # a descriptor sits two levels below


def frame_rows(bundle: Mapping[str, Any]) -> Iterator[dict[str, JsonValue]]:
    """Yield one row for each frame entry of a bundle record, holding only the facts it holds."""
    identity = bundle.get("identity")
    if not isinstance(identity, Mapping):
        return
    for entry in identity.get("frames", []):
        if isinstance(entry, Mapping) and (row := _row(bundle, identity, entry)):
            yield row


def _row(
    bundle: Mapping[str, Any], identity: Mapping[str, Any], entry: Mapping[str, Any]
) -> dict[str, JsonValue]:
    row: dict[str, JsonValue] = {STREAM_KEY: bundle[STREAM_KEY]} if STREAM_KEY in bundle else {}
    if "frame_index" in entry:
        row["frame_index"] = entry["frame_index"]
        row["content_frame_index"] = content_frame_index(entry)
    row |= {key: entry[key] for key in _ENTRY_KEYS if key in entry}
    row |= {key: identity[key] for key in LAYOUT_KEYS if key in identity}
    if row.keys() >= _PATH_KEYS:
        name = frame_name(int(str(row["frame_index"])), str(row["pixel_format"]))
        row["path"] = f"{_FRAMES_FROM_DESCRIPTOR}/{row[STREAM_KEY]}/{name}"
    if "generated" in bundle:
        row["generated"] = bundle["generated"] is not None
    return row
