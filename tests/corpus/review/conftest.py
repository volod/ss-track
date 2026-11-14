"""Review tests stage the pool version once per test and run discovery over it."""

from pathlib import Path

import pytest

from ss_track.corpus import ImportResult
from tests.corpus.review._review import stage_pool


@pytest.fixture
def pool(
    media: Path, data_root: Path, first: ImportResult, second: ImportResult, third: ImportResult
) -> tuple[ImportResult, ImportResult, ImportResult]:
    stage_pool(media, data_root, first, second, third)
    return first, second, third
