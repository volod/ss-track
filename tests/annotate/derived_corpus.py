"""One built corpus with two generated cases and frozen parent labels, for derivation tests."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.compare import compare_label_sets
from ss_track.cli import main
from ss_track.corpus import build_corpus, import_source
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations
from tests.annotate.review_files import (
    decision_for,
    freeze_written,
    prepare_pair,
    write_review,
    write_settlement,
)
from tests.annotate.support import DRAFT
from tests.corpus._media import write_clip
from tests.corpus.conftest import (
    case_of,
    encounter_of,
    group_of,
    recording_declaration,
    stream_of,
    write_groups,
)

CORPUS = "pilot-v1"
STREAM = "one"
_AWAY = {"x": 40, "y": 30, "width": 10, "height": 10}


def build_frozen_corpus(root: Path, pack: ScenarioPack) -> tuple[Path, Path, Path]:
    """Import one clip, build a shake and an absence case, and freeze the parent labels.

    Return the data root, the clip and the folder that holds the frozen pair.
    """
    media = root / "media"
    media.mkdir()
    clip = write_clip(media / "clip.mkv")
    recording = media / "recording.yaml"
    recording.write_text(yaml.safe_dump(recording_declaration()), encoding="utf-8")
    data = root / "data"
    imported = import_source(recording, data)
    absence = case_of(
        "absence", "target_absence", 1, {"region": _AWAY, "plate_frame": 0, "noise": 2}
    )
    shake = case_of("shake", "camera_shake", 1, {"amplitude": 2})
    stream = stream_of(imported, generated_cases=[absence, shake])
    groups = [group_of("group-one", "development", encounter_of("enc-one", stream))]
    build_corpus(write_groups(media, groups), data)
    folder = root / "frozen"
    left, right = prepare_pair(folder, pack, clip, lambda _body: None)
    write_review(folder)
    write_settlement(folder, [decision_for(row, "left") for row in compare_label_sets(left, right)])
    freeze_written(folder, clip)
    return data, clip, folder


def derive(
    data: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, *, code: int = 0
) -> dict[str, Any]:
    caplog.set_level(logging.INFO)
    caplog.clear()
    monkeypatch.setenv("DATA_DIR", str(data))
    assert main(["annotate", "derive", "--corpus", CORPUS, "--pack", str(DRAFT)]) == code
    loaded = json.loads(caplog.records[-1].getMessage())
    if not isinstance(loaded, dict):
        raise TypeError("command record is not an object")
    return loaded


def install_labels(data: Path, folder: Path) -> None:
    dest = data / "corpus" / CORPUS / "labels" / STREAM
    dest.mkdir(parents=True)
    shutil.copy(folder / "frozen.json", dest / "labels.json")
    shutil.copy(folder / "revision.json", dest / "revision.json")


def copy_data(source: Path, dest: Path) -> Path:
    copied = dest / "data"
    shutil.copytree(source, copied)
    return copied


def assert_command(record: dict[str, Any]) -> None:
    contracts = load_contract_set()
    contract = contracts.named("result/command")
    frozen = contract.versions[-1]
    found = violations(
        record, contracts.frozen_schema(contract, frozen), contracts.schema_registry()
    )
    assert not found, found
    _no_score(record)


def _no_score(value: object) -> None:
    if isinstance(value, dict):
        assert "score" not in value
        for child in value.values():
            _no_score(child)
    elif isinstance(value, list):
        for child in value:
            _no_score(child)
