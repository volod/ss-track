"""Feature rows as a selection reads them: per run extractor and stream, rows keyed by frame index.

A window reads the rows of the embedded frames inside it. Its descriptor is the unit mean of those
rows, and a stream's background is the unit mean of all its rows: the frozen backbone's account of
what the stream usually shows. Rows are unit float32 values read as float64.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from ss_track.corpus.discovery.features import FeatureFile


def unit(vector: np.ndarray) -> np.ndarray:
    """Return a vector scaled to length 1, or itself when it has no length."""
    norm = float(np.linalg.norm(vector))
    return vector if norm == 0.0 else vector / norm


@dataclass(frozen=True, slots=True)
class StreamEmbedding:
    """One run extractor's rows of one stream, in frame order."""

    frames: np.ndarray  # frame indexes, ascending
    rows: np.ndarray  # one unit row per frame

    def window(self, start: int, end: int) -> np.ndarray:
        """Return the rows of the embedded frames in a half-open window."""
        first, last = np.searchsorted(self.frames, [start, end])
        rows: np.ndarray = self.rows[first:last]
        return rows

    def background(self) -> np.ndarray:
        """Return the unit mean of every row of the stream."""
        return unit(self.rows.mean(axis=0))


def stream_embeddings(
    features: Mapping[str, FeatureFile],
) -> dict[tuple[str, str], StreamEmbedding]:
    """Key every feature record's rows by run extractor and stream."""
    found: dict[tuple[str, str], StreamEmbedding] = {}
    for feature in features.values():
        record: Any = feature.record
        rows = np.frombuffer(feature.vectors, dtype="<f4").astype(np.float64)
        frames = np.array([row["frame_index"] for row in record["rows"]], dtype=np.int64)
        found[(feature.extractor_id, feature.stream_id)] = StreamEmbedding(
            frames, rows.reshape(len(frames), int(record["dimensions"]))
        )
    return found
