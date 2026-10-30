"""Stable project identity used by the starter API and CLI."""

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

DISTRIBUTION_NAME = "agent-python-project"
PACKAGE_NAME = "agent_py"
FALLBACK_VERSION = "0.0.0+uninstalled"


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """Public identity for diagnostics and smoke checks."""

    distribution: str
    package: str
    version: str


def project_info() -> ProjectInfo:
    """Return installed project metadata without failing from a source-only checkout."""
    try:
        installed_version = version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        installed_version = FALLBACK_VERSION
    return ProjectInfo(
        distribution=DISTRIBUTION_NAME,
        package=PACKAGE_NAME,
        version=installed_version,
    )
