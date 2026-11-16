"""Development event edits re-pin; released descriptors remain immutable."""

import shutil
from pathlib import Path

import pytest
import yaml

from ss_track.contract import build
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.store import default_root


@pytest.fixture
def private_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "contracts"
    shutil.copytree(default_root(), root)
    proto = tmp_path / "proto"
    shutil.copytree(build.PROTO_ROOT, proto)
    gen = tmp_path / "gen"
    shutil.copytree(build._GEN_ROOT, gen)
    monkeypatch.setattr(build, "PROTO_ROOT", proto)
    monkeypatch.setattr(build, "_GEN_ROOT", gen)
    path = proto / "frame.proto"
    source = path.read_text()
    edited = source.replace(
        'string stream_id = 1 [json_name = "stream_id"];',
        'string stream = 1 [json_name = "stream"];',
    )
    assert edited != source
    path.write_text(edited)
    return root


def test_development_edit_regenerates_and_repins(private_set: Path) -> None:
    before = (private_set / "event/frame/1.0.0.binpb").read_bytes()
    build.write_artifacts(private_set)
    assert (private_set / "event/frame/1.0.0.binpb").read_bytes() != before
    assert check_contract_set(private_set) == []
    assert build.drift_findings(private_set) == []


def test_released_edit_is_refused(private_set: Path) -> None:
    registry_path = private_set / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_bytes())
    registry["stage"] = "released"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False))
    before = (private_set / "event/frame/1.0.0.binpb").read_bytes()
    with pytest.raises(ValueError, match="frozen descriptor differs"):
        build.write_artifacts(private_set)
    assert (private_set / "event/frame/1.0.0.binpb").read_bytes() == before


def test_second_development_version_fails_stage_check(private_set: Path) -> None:
    path = private_set / "registry.yaml"
    registry = yaml.safe_load(path.read_bytes())
    entry = next(item for item in registry["contracts"] if item["family"] == "event")
    entry["versions"].append(entry["versions"][0] | {"version": "1.1.0"})
    path.write_text(yaml.safe_dump(registry, sort_keys=False))
    assert any(
        "development stage holds one version" in f for f in build.drift_findings(private_set)
    )
    with pytest.raises(ValueError, match="development stage holds one version"):
        build.write_artifacts(private_set)


def test_check_refuses_unpinned_descriptor(private_set: Path) -> None:
    build.write_artifacts(private_set)
    path = private_set / "registry.yaml"
    registry = yaml.safe_load(path.read_bytes())
    entry = next(
        item
        for item in registry["contracts"]
        if item["id"] == "frame" and item["family"] == "event"
    )
    entry["versions"][0]["file_sha256"] = "0" * 64
    path.write_text(yaml.safe_dump(registry, sort_keys=False))
    assert any("frozen file was edited" in item for item in build.drift_findings(private_set))


def test_development_regenerates_missing_image(private_set: Path) -> None:
    image = private_set / "event/frame/1.0.0.binpb"
    image.unlink()
    build.write_artifacts(private_set)
    assert image.is_file()
    assert check_contract_set(private_set) == []


def test_released_matching_images_are_not_rewritten(private_set: Path) -> None:
    registry_path = private_set / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_bytes())
    registry["stage"] = "released"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False))
    source = build.PROTO_ROOT / "frame.proto"
    source.write_text(
        source.read_text().replace(
            'string stream = 1 [json_name = "stream"];',
            'string stream_id = 1 [json_name = "stream_id"];',
        )
    )
    image = private_set / "event/frame/1.0.0.binpb"
    before = image.stat().st_mtime_ns
    build.write_artifacts(private_set)
    assert image.stat().st_mtime_ns == before
