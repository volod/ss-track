from unittest.mock import patch

from agent_py.metadata import (
    DISTRIBUTION_NAME,
    FALLBACK_VERSION,
    PACKAGE_NAME,
    project_info,
)


def test_project_info_reports_distribution_package_and_installed_version() -> None:
    with patch("agent_py.metadata.version", return_value="1.2.3"):
        info = project_info()

    assert info.distribution == DISTRIBUTION_NAME
    assert info.package == PACKAGE_NAME
    assert info.version == "1.2.3"


def test_project_info_has_a_source_checkout_fallback() -> None:
    from importlib.metadata import PackageNotFoundError

    with patch("agent_py.metadata.version", side_effect=PackageNotFoundError):
        info = project_info()

    assert info.version == FALLBACK_VERSION
