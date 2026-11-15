"""Shared annotation fixtures. The rotated clip is encoded once per module."""

from pathlib import Path

import pytest

from ss_track.annotate.pack import load_scenario_pack
from ss_track.annotate.pack_model import ScenarioPack
from tests.annotate.support import DRAFT
from tests.corpus._media import write_rotated_clip


@pytest.fixture(scope="module")
def pack() -> ScenarioPack:
    """Return the draft aerial pack."""
    return load_scenario_pack(DRAFT)


@pytest.fixture(scope="module")
def rotated_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return one video whose display rotation is recorded and whose pixels stay upright."""
    return write_rotated_clip(tmp_path_factory.mktemp("media") / "rotated.mp4", 90)
