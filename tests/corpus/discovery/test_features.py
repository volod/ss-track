"""A feature-rows record seals its row keys and its vector file, and holds its example's bytes."""

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.discovery.features import feature_findings, read_vectors
from tests.corpus.discovery._feature_example import DIMENSIONS, golden_feature_file
from tests.corpus.discovery._records import written_form

EXAMPLES = Path(__file__).parents[2] / "schema" / "examples"


def test_the_golden_feature_record_matches_its_example() -> None:
    feature = golden_feature_file()

    assert written_form(feature.record) == (EXAMPLES / "record-feature-rows.json").read_text()
    assert feature.line()["row_count"] == 3
    assert feature.name == "features/clip-b16/one.json"


def test_rows_out_of_order_or_a_wrong_size_are_findings() -> None:
    record: Any = dict(golden_feature_file().record)
    record["rows"] = list(reversed(record["rows"]))
    record["vectors"] = record["vectors"] | {"size_bytes": 4}

    found = {(item.pointer, item.rule) for item in feature_findings(record, "rows")}

    assert found == {("/rows/1", "order"), ("/rows/2", "order"), ("/vectors/size_bytes", "vectors")}


def test_vector_bytes_are_read_only_when_they_are_the_sealed_ones(tmp_path: Path) -> None:
    feature = golden_feature_file()
    (tmp_path / "one.f32").write_bytes(feature.vectors)

    assert read_vectors(tmp_path, feature.record) == feature.vectors

    (tmp_path / "one.f32").write_bytes(bytes(len(feature.vectors)))
    with pytest.raises(CorpusRefusal) as caught:
        read_vectors(tmp_path, feature.record)
    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_a_non_finite_value_is_refused(tmp_path: Path) -> None:
    vectors = np.full(3 * DIMENSIONS, np.nan, dtype="<f4").tobytes()
    record: Any = dict(golden_feature_file().record)
    record["vectors"] = record["vectors"] | {"sha256": sha256_bytes(vectors)}
    (tmp_path / "one.f32").write_bytes(vectors)

    with pytest.raises(CorpusRefusal) as caught:
        read_vectors(tmp_path, record)
    assert caught.value.code is RefusalCode.RECORD_INVALID
