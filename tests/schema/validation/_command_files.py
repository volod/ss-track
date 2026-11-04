"""The kept frame set, altered copies of it and the refusal they meet, for the command tests."""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema import validate_file
from tests._sealing import self_sealed
from tests.schema.conftest import (
    KEPT_FRAME_SET,
)

FRAME_SET_CONTRACT = "record/frame-set"
FRAME_SET_URN = "urn:ss-track:contract:record:frame-set:1.0.0"


def kept_record() -> dict[str, Any]:
    record: dict[str, Any] = json.loads(KEPT_FRAME_SET.read_text(encoding="ascii"))
    return record


def write_json(tmp_path: Path, record: object, name: str = "record.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(record), encoding="ascii")
    return path


def resealed(record: dict[str, Any]) -> dict[str, Any]:
    """Return a record consistent with itself, so only its structure can refuse it."""
    return self_sealed({key: value for key, value in record.items() if key != "manifest_sha256"})


def refused_validation(path: Path, **options: Any) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        validate_file(path, **options)
    return caught.value
