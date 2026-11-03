"""A benchmark fixture: a sealed read of a million-frame index walks no contract.

`corpus verify` opens every bundle record before it hashes a frame. Contracts are enforced before a
record is sealed, never on a read, so opening the largest record a corpus holds costs what it did
before enforcement. The fixture is a real kept bundle with its index grown to a million frames.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.canonical import SEAL_FIELD
from ss_track.corpus import open_frame_bundle
from ss_track.corpus.frames import bundle_hash
from ss_track.schema import strict
from tests._sealing import self_sealed
from tests.corpus._historic import RECORDS

MILLION = 1_000_000
_FRAME_STEP_PTS = 40


@pytest.fixture(scope="module")
def million_frame_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write a sealed bundle record whose index holds a million frames."""
    kept = RECORDS / "bundle-schema-3-d6b704d.json"
    record: dict[str, Any] = json.loads(kept.read_text(encoding="ascii"))
    record.pop(SEAL_FIELD)
    identity = record["identity"]
    digest = identity["frames"][0]["sha256"]
    identity["frames"] = [
        {"frame_index": index, "pts": index * _FRAME_STEP_PTS, "sha256": digest}
        for index in range(MILLION)
    ]
    identity["selection"] = {"start_frame": 0, "end_frame": MILLION}
    record["bundle_sha256"] = bundle_hash(identity)
    directory = tmp_path_factory.mktemp("million") / "stream"
    directory.mkdir()
    (directory / "manifest.json").write_text(json.dumps(self_sealed(record)), encoding="ascii")
    return directory


def test_opening_a_million_frame_index_validates_nothing(
    million_frame_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def walked(*_: object, **__: object) -> None:
        raise AssertionError("a sealed read walked a contract")

    monkeypatch.setattr(strict.StrictValidator, "iter_errors", walked)

    bundle = open_frame_bundle(million_frame_bundle)

    assert len(bundle) == MILLION
