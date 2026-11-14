"""`make ci` runs the lightweight group, and the other group stays available locally."""

import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import tests.core.test_paths as paths
import tests.corpus.descriptors.test_descriptor as descriptors
import tests.corpus.descriptors.test_public_descriptor as public_descriptors
import tests.corpus.records.test_read_window as read_window
import tests.corpus.siblings.test_sibling_defects as sibling_defects
import tests.schema.compatibility.test_dispositions as dispositions
import tests.schema.compatibility.test_history as history
import tests.schema.registry.test_check as contract_checks
from tests.grouping import function_is_external

_ROOT = Path(__file__).resolve().parents[2]
_EXTERNAL: tuple[tuple[ModuleType, str], ...] = (
    (contract_checks, "test_the_shipped_set_passes"),
    (history, "test_unchanged_history_passes"),
    (history, "test_ci_has_history_and_explicit_event_baseline"),
    (dispositions, "test_no_installed_major_is_a_view_yet"),
    (dispositions, "test_freeze_refuses_a_view_of_a_major_that_adds_an_operator_judgment"),
    (read_window, "test_a_facts_major_is_refused_as_evidence_and_stays_inspectable"),
    (sibling_defects, "test_a_download_attempt_writes_to_standard_output"),
    (descriptors, "test_croissant_loads_all_record_sets"),
)
_LIGHT: tuple[tuple[ModuleType, str], ...] = (
    (paths, "test_default_is_below_the_project_root"),
    (descriptors, "test_cli_describe_and_refusal"),
    (public_descriptors, "test_public_descriptor_projects_non_locked_fields"),
)


def _recipe(makefile: str, target: str) -> str:
    found = re.search(rf"^{target}:.*(?:\n\t.*)+", makefile, re.MULTILINE)
    assert found is not None
    return found.group(0)


def test_contract_artifacts_and_optional_runtimes_are_the_external_group() -> None:
    assert all(function_is_external(module, name) for module, name in _EXTERNAL)
    assert not any(function_is_external(module, name) for module, name in _LIGHT)


def test_collection_marks_only_the_external_group() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "tests/schema/registry/test_check.py",
            "tests/core/test_paths.py",
            "-m",
            "external",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=_ROOT,
    )

    assert "test_check.py::" in completed.stdout
    assert "test_paths.py::" not in completed.stdout


def test_make_ci_runs_the_light_group_and_test_runs_both() -> None:
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert re.search(r"^ci: ci-checks test-light\b", makefile, re.MULTILINE)
    assert re.search(r"^ci-github: ci\b", makefile, re.MULTILINE)
    assert "make ci-github" in workflow
    assert '-m "not external"' in _recipe(makefile, "test-light")
    assert "-m external" in _recipe(makefile, "test-external")
    assert "external" not in _recipe(makefile, "test")
    assert "external" not in _recipe(makefile, "coverage")
