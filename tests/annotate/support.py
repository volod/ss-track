"""Load a copy of the draft pack after one test changes it."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.annotate.pack import load_scenario_pack
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from tests.schema.conftest import PROJECT_ROOT

DRAFT = PROJECT_ROOT / "scenarios" / "packs" / "aerial-small-objects.yaml"
EXAMPLE = PROJECT_ROOT / "tests" / "schema" / "examples" / "declaration-scenario-pack.json"


def document() -> dict[str, Any]:
    """Return the draft pack as a mapping a test may change."""
    loaded = yaml.safe_load(DRAFT.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("draft pack is not a mapping")
    return loaded


def write_pack(tmp_path: Path, body: dict[str, Any]) -> Path:
    """Write one pack where the loader will read it."""
    path = tmp_path / "pack.yaml"
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


def changed(tmp_path: Path, mutate: Callable[[dict[str, Any]], None]) -> Path:
    """Write the draft after `mutate` edits it."""
    body = document()
    mutate(body)
    return write_pack(tmp_path, body)


def envelope(*, approved: bool) -> dict[str, Any]:
    """Return one living-subject envelope. Without approval the pack must be refused."""
    body: dict[str, Any] = {
        "kind": "living",
        "d_min_m": 50,
        "d_alert_m": 80,
        "v_close_max_m_s": 1,
        "approach_sectors": [
            {
                "sector_id": "all",
                "bearing_start_deg": 0,
                "bearing_end_deg": 360,
                "elevation_min_deg": -10,
                "elevation_max_deg": 30,
            }
        ],
        "exclusion_zones": [],
        "t_follow_max_s": 600,
        "end_conditions": ["episode-end"],
    }
    if approved:
        body["approval"] = {"owner": "ada", "reference": "rec-1"}
    return body


def refused(path: Path, reason: str) -> CorpusRefusal:
    """Return the refusal, which must name `reason`."""
    with pytest.raises(CorpusRefusal, match=reason) as caught:
        load_scenario_pack(path)
    refusal: CorpusRefusal = caught.value
    assert refusal.code is RefusalCode.MANIFEST_INVALID
    return refusal
