"""The plan requires one pinned decoder with arm64 wheels; these checks keep that true."""

import tomllib
from pathlib import Path

import pytest

from ss_track.quality.project_root import discover_project_root

ROOT = discover_project_root(Path(__file__).parent)
ARM64_MARKERS = ("manylinux_2_28_aarch64", "macosx_14_0_arm64")


def _wheels(package: str) -> list[str]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    entry = next(item for item in lock["package"] if item["name"] == package)
    return [wheel["url"].rsplit("/", 1)[1] for wheel in entry["wheels"]]


def test_decoder_is_pinned_to_one_exact_version() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    pins = [item for item in project["project"]["dependencies"] if item.startswith("av")]

    assert len(pins) == 1
    assert "==" in pins[0]


@pytest.mark.parametrize("marker", ARM64_MARKERS)
def test_locked_decoder_has_arm64_wheels(marker: str) -> None:
    assert any("abi3" in name and marker in name for name in _wheels("av"))


@pytest.mark.parametrize("python_tag", ["cp312", "cp313"])
def test_locked_yaml_parser_has_arm64_wheels(python_tag: str) -> None:
    assert any(python_tag in name and "aarch64" in name for name in _wheels("pyyaml"))
