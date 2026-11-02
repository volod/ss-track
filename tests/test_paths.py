from pathlib import Path

import pytest

from ss_track.paths import resolve_data_root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").touch()
    (tmp_path / "AGENTS.md").touch()
    return tmp_path


def test_default_is_below_the_project_root(project: Path) -> None:
    assert resolve_data_root({}, project) == project / ".data"


def test_nested_start_still_finds_the_project_root(project: Path) -> None:
    nested = project / "a" / "b"
    nested.mkdir(parents=True)

    assert resolve_data_root({}, nested) == project / ".data"


def test_environment_value_wins(project: Path, tmp_path: Path) -> None:
    (project / ".env").write_text("DATA_DIR=from-file\n", encoding="utf-8")

    assert resolve_data_root({"DATA_DIR": "from-env"}, project) == project / "from-env"


def test_absolute_environment_value_is_kept(project: Path, tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"

    assert resolve_data_root({"DATA_DIR": str(target)}, project) == target


@pytest.mark.parametrize(
    "line",
    ["DATA_DIR=runs", "export DATA_DIR=runs", 'DATA_DIR="runs"', "DATA_DIR='runs'"],
)
def test_env_file_forms(project: Path, line: str) -> None:
    (project / ".env").write_text(f"# comment\nOTHER=x\n{line}\n", encoding="utf-8")

    assert resolve_data_root({}, project) == project / "runs"


def test_last_env_file_assignment_wins(project: Path) -> None:
    (project / ".env").write_text("DATA_DIR=first\nDATA_DIR=second\n", encoding="utf-8")

    assert resolve_data_root({}, project) == project / "second"


def test_empty_values_fall_through_to_the_default(project: Path) -> None:
    (project / ".env").write_text("DATA_DIR=\n", encoding="utf-8")

    assert resolve_data_root({"DATA_DIR": ""}, project) == project / ".data"


def test_outside_a_project_the_start_directory_is_the_base(tmp_path: Path) -> None:
    assert resolve_data_root({}, tmp_path) == tmp_path / ".data"
