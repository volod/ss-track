"""The golden feature-rows record: three rows of four values for stream `one` of the golden run."""

import numpy as np

from ss_track.core.canonical import sha256_bytes
from ss_track.corpus.discovery.features import FeatureFile, seal_feature_rows
from ss_track.corpus.siblings.embedding import StreamRows
from tests.corpus.discovery._run_body import CORPUS_ID, RUN_ID

DIMENSIONS = 4
STRIDE = 8


def golden_feature_file() -> FeatureFile:
    """Rows for frames 0, 8 and 16 of a 24-frame bundle, each a unit vector along one axis."""
    vectors = np.eye(3, DIMENSIONS, dtype="<f4").tobytes()
    keys = tuple((index, sha256_bytes(f"frame-{index}".encode("ascii"))) for index in (0, 8, 16))
    rows = StreamRows("one", sha256_bytes(b"b-one"), keys, vectors)
    return seal_feature_rows(RUN_ID, CORPUS_ID, "clip-b16", rows, STRIDE, DIMENSIONS)
