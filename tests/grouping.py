"""Two test groups. `make ci` runs only the lightweight one.

A test is external when its module rechecks the shipped contract set, builds a Git history of
that set, or is the real sibling-release probe. A test that refuses to start without the optional
Croissant package is external as well. Everything else is lightweight and has no external artifact
dependency.
"""

import inspect
from types import ModuleType

import pytest

_CONTRACT_ARTIFACTS = (
    "check_contract_set",
    "history_findings",
    "freeze_contract",
    "freeze_next",
    "private_contracts",
)
_SIBLING_PROBES = "test_sibling_defects.py"
_CROISSANT_SKIP = 'importorskip("mlcroissant")'
_MODULE_EXTERNAL: dict[ModuleType, bool] = {}


def _module_is_external(module: ModuleType) -> bool:
    cached = _MODULE_EXTERNAL.get(module)
    if cached is not None:
        return cached
    filename = getattr(module, "__file__", "") or ""
    external = filename.endswith(_SIBLING_PROBES) or any(
        name in inspect.getsource(module) for name in _CONTRACT_ARTIFACTS
    )
    _MODULE_EXTERNAL[module] = external
    return external


def function_is_external(module: ModuleType, test_name: str) -> bool:
    """Return whether one test function belongs in the external group."""
    if _module_is_external(module):
        return True
    if not test_name.startswith("test_croissant"):
        return False
    function = getattr(module, test_name, None)
    if function is None:
        return False
    return _CROISSANT_SKIP in inspect.getsource(function)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark the external group so `make ci` can select the lightweight complement."""
    for item in items:
        module = getattr(item, "module", None)
        name = getattr(item, "originalname", None)
        if (
            isinstance(module, ModuleType)
            and isinstance(name, str)
            and function_is_external(module, name)
        ):
            item.add_marker(pytest.mark.external)
