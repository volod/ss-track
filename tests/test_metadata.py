import tomllib
from pathlib import Path
from unittest.mock import patch

from ss_track.metadata import (
    DISTRIBUTION_NAME,
    FALLBACK_VERSION,
    PACKAGE_NAME,
    project_info,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_packaging_metadata_declares_the_same_identity() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == DISTRIBUTION_NAME
    assert pyproject["project"]["scripts"][DISTRIBUTION_NAME] == f"{PACKAGE_NAME}.cli:main"


def test_project_info_reports_distribution_package_and_installed_version() -> None:
    with patch("ss_track.metadata.version", return_value="1.2.3"):
        info = project_info()

    assert info.distribution == DISTRIBUTION_NAME
    assert info.package == PACKAGE_NAME
    assert info.version == "1.2.3"


def test_project_info_has_a_source_checkout_fallback() -> None:
    from importlib.metadata import PackageNotFoundError

    with patch("ss_track.metadata.version", side_effect=PackageNotFoundError):
        info = project_info()

    assert info.version == FALLBACK_VERSION
