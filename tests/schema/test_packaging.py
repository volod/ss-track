"""The contracts travel with the tool: a wheel built the way `uv build` builds one carries them."""

import json
import shutil
import subprocess
import sys
import tarfile
import textwrap
import tomllib
import zipfile
from pathlib import Path

import pytest

from ss_track.schema.store import CONTRACT_FILES_PACKAGE, default_root
from tests.schema.conftest import CONTRACTS, KEPT_FRAME_SET, PROJECT_ROOT

_SOURCE = PROJECT_ROOT / "src"
_BUILD = """
import sys
from setuptools import build_meta
step, target = sys.argv[1], sys.argv[2]
print(getattr(build_meta, step)(target))
"""


def _pyproject() -> dict[str, object]:
    return tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_every_package_is_listed_because_a_mapping_rules_out_discovery() -> None:
    listed = _pyproject()["tool"]["setuptools"]["packages"]  # type: ignore[index]
    found = {
        ".".join(path.parent.relative_to(_SOURCE).parts) for path in _SOURCE.rglob("__init__.py")
    }

    assert set(listed) == found | {CONTRACT_FILES_PACKAGE}  # type: ignore[arg-type]


def test_a_checkout_reads_the_root_directory() -> None:
    assert default_root() == CONTRACTS


def _isolated_copy(target: Path) -> Path:
    """Copy what a build reads, so no build output lands in the checkout."""
    project = target / "project"
    project.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy(PROJECT_ROOT / name, project / name)
    ignored = shutil.ignore_patterns("__pycache__", "*.egg-info")
    shutil.copytree(CONTRACTS, project / "contracts", ignore=ignored)
    shutil.copytree(_SOURCE, project / "src", ignore=ignored)
    return project


def _build(step: str, project: Path, target: Path) -> Path:
    target.mkdir(exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-c", _BUILD, step, str(target)],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    return target / completed.stdout.strip().splitlines()[-1]


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a wheel from a source distribution, as uv does, and unpack it outside the checkout."""
    base = tmp_path_factory.mktemp("wheel")
    sdist = _build("build_sdist", _isolated_copy(base), base / "dist")
    with tarfile.open(sdist) as archive:
        archive.extractall(base / "unpacked", filter="data")
    wheel = _build("build_wheel", next((base / "unpacked").iterdir()), base / "dist")
    site = base / "site"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(site)
    return site


def _run(site: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the installed command with the wheel first on the path and no checkout in reach."""
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(site)!r})
        import ss_track
        assert ss_track.__file__.startswith({str(site)!r}), ss_track.__file__
        from ss_track.cli import main
        raise SystemExit(main({argv!r}))
        """
    )
    return subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=site, capture_output=True, text=True, check=False
    )


def test_the_wheel_carries_the_whole_set(installed: Path) -> None:
    packaged = installed / "ss_track" / "contract_files"
    shipped = {
        path.relative_to(CONTRACTS)
        for path in CONTRACTS.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }

    assert {path.relative_to(packaged) for path in packaged.rglob("*") if path.is_file()} == shipped


def test_the_wheel_lists_its_contracts_outside_the_checkout(installed: Path) -> None:
    completed = _run(installed, ["contracts", "list"])

    assert completed.returncode == 0, completed.stderr
    record = json.loads(completed.stderr.strip().splitlines()[-1])
    assert record["root"].startswith(str(installed))
    assert {item["contract"] for item in record["contracts"]} >= {"record/frame-set"}


def test_a_real_frame_set_validates_from_the_wheel_with_no_byte_changed(
    installed: Path, tmp_path: Path
) -> None:
    held = tmp_path / "frame-set.json"
    shutil.copy(KEPT_FRAME_SET, held)
    before = held.read_bytes()

    completed = _run(installed, ["contracts", "validate", "--file", str(held)])

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stderr.strip().splitlines()[-1])["status"] == "valid"
    assert held.read_bytes() == before


def test_an_altered_frame_set_is_refused_from_the_wheel(installed: Path, tmp_path: Path) -> None:
    record = json.loads(KEPT_FRAME_SET.read_text(encoding="ascii"))
    record["surprise"] = 1
    held = tmp_path / "frame-set.json"
    held.write_text(json.dumps(record), encoding="ascii")

    completed = _run(installed, ["contracts", "validate", "--file", str(held)])

    assert completed.returncode == 1
    assert json.loads(completed.stderr.strip().splitlines()[-1])["code"] == "RECORD_INVALID"


def test_the_contract_package_stays_below_the_corpus() -> None:
    """The corpus writers validate through this package, so the reverse import would be a cycle."""
    modules = sorted(path.stem for path in (_SOURCE / "ss_track" / "schema").glob("[a-z]*.py"))
    code = "\n".join(
        [
            "import sys",
            *(f"import ss_track.schema.{name}" for name in modules),
            'print(sorted(name for name in sys.modules if name.startswith("ss_track.corpus")))',
            'print("av" in sys.modules)',
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert "check" in modules
    assert completed.stdout.split("\n")[:2] == ["[]", "False"]
