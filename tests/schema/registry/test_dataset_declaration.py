"""The dataset declaration requires the discovery facts an operator must supply."""

import json
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.schema.validation.enforce import read_declaration
from tests.schema.conftest import EXAMPLES


@pytest.mark.parametrize(
    "missing", ["title", "description", "license", "citation", "address", "publication_date"]
)
def test_missing_discovery_fact_is_refused(tmp_path: Path, missing: str) -> None:
    example = EXAMPLES / "declaration-dataset.json"
    declaration = json.loads(example.read_text())
    del declaration[missing]
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(declaration))
    with pytest.raises(CorpusRefusal) as caught:
        read_declaration(path, "declaration/dataset", 1)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert missing in str(caught.value.details)
