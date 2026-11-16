"""Annotation: scenario packs, labels, seeds, masks, review and generated-case labels."""

from ss_track.annotate.packs.load import load_scenario_pack
from ss_track.annotate.packs.model import ScenarioPack

__all__ = ["ScenarioPack", "load_scenario_pack"]
