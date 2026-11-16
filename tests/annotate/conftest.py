"""Shared annotation fixtures. The clips and the built corpus are made once per module."""

from pathlib import Path

import pytest

from ss_track.annotate.packs.load import load_scenario_pack
from ss_track.annotate.packs.model import ScenarioPack
from tests.annotate.derived_corpus import build_frozen_corpus
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


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory, pack: ScenarioPack) -> tuple[Path, Path, Path]:
    """Return a built corpus's data root, its clip and the folder of that clip's frozen pair."""
    return build_frozen_corpus(tmp_path_factory.mktemp("derive-built"), pack)
