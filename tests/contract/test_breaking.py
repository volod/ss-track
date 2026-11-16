"""Wire and JSON compatibility fails closed, and an added field does not."""

import shutil
from pathlib import Path

from ss_track.contract.breaking import BUF_CONFIG, PROTO_ROOT, breaking_findings
from ss_track.contract.build import build_image, drift_findings
from ss_track.schema.compatibility.versioning import _event_bump
from ss_track.schema.registry.contract import MAJOR, MINOR, PATCH

_FROZEN = Path(__file__).resolve().parents[2] / "contracts" / "event" / "frame" / "1.0.0.binpb"
_URN = "urn:ss-track:contract:event:frame:1.0.0"


def _module(tmp_path: Path, source: str) -> Path:
    root = tmp_path / "module"
    root.mkdir(parents=True)
    (root / "frame.proto").write_text(source, encoding="utf-8")
    shutil.copy(PROTO_ROOT / "contract_options.proto", root / "contract_options.proto")
    shutil.copy(BUF_CONFIG, root / "buf.yaml")
    return root


def _source(old: str, new: str) -> str:
    text = (PROTO_ROOT / "frame.proto").read_text(encoding="utf-8")
    found = text.replace(old, new, 1)
    assert found != text
    return found


def test_committed_descriptors_match_the_proto_sources() -> None:
    assert drift_findings() == []


def test_a_renamed_field_fails_the_gate(tmp_path: Path) -> None:
    source = _source(
        'string stream_id = 1 [json_name = "stream_id"];',
        'string stream = 1 [json_name = "stream"];',
    )

    assert breaking_findings(_module(tmp_path, source), _FROZEN)


def test_a_reused_field_number_fails_the_gate(tmp_path: Path) -> None:
    source = _source(
        'string stream_id = 1 [json_name = "stream_id"];',
        'string stream_id = 16 [json_name = "stream_id"];\n  string other = 1 [json_name = "other"];',
    )

    assert breaking_findings(_module(tmp_path, source), _FROZEN)


def test_a_changed_json_name_fails_the_gate(tmp_path: Path) -> None:
    source = _source('json_name = "stream_id"', 'json_name = "streamId"')

    assert breaking_findings(_module(tmp_path, source), _FROZEN)


def test_an_added_field_and_a_comment_do_not_break(tmp_path: Path) -> None:
    added = _source(
        'string sha256 = 15 [json_name = "sha256"];',
        'string sha256 = 15 [json_name = "sha256"];\n  optional string note = 16 [json_name = "note"];',
    )
    comment = _source("One staged frame", "One staged picture")

    assert breaking_findings(_module(tmp_path / "added", added), _FROZEN) == []
    assert breaking_findings(_module(tmp_path / "comment", comment), _FROZEN) == []


def test_the_bump_follows_wire_compatibility(tmp_path: Path) -> None:
    added = _source(
        'string sha256 = 15 [json_name = "sha256"];',
        'string sha256 = 15 [json_name = "sha256"];\n  optional string note = 16 [json_name = "note"];',
    )
    renamed = _source(
        'string stream_id = 1 [json_name = "stream_id"];',
        'string stream = 1 [json_name = "stream"];',
    )
    comment = _source("One staged frame", "One staged picture")
    images = {}
    for name, source in (("added", added), ("renamed", renamed), ("comment", comment)):
        module = _module(tmp_path / name, source)
        image = tmp_path / f"{name}.binpb"
        build_image(module, "frame.proto", image)
        images[name] = image

    assert _event_bump(_FROZEN, images["added"], _URN, _URN) == MINOR
    assert _event_bump(_FROZEN, images["renamed"], _URN, _URN) == MAJOR
    assert _event_bump(_FROZEN, images["comment"], _URN, _URN) == PATCH
