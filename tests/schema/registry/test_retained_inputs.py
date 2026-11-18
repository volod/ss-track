"""Retained operator inputs follow the installed declaration contracts (spec section 17.7).

Operator-written inputs are not regenerable, so a development edit that changes a declaration's
shape edits every retained one in the same change. These are the inputs the repository keeps;
an edit that forgets one fails here instead of at the next regeneration.
"""

import pytest

from ss_track.schema.validation.enforce import installed_contracts, read_declaration
from tests.schema.conftest import PROJECT_ROOT

RETAINED_FOLDERS = ("docs/impl/workloads", "scenarios")
RETAINED = {
    "docs/impl/workloads/hawk-drone/corpus.yaml": "declaration/corpus",
    "docs/impl/workloads/hawk-drone/recording.yaml": "declaration/recording",
    "docs/impl/workloads/two-source-pilot/inventory-additions.yaml": "declaration/source-inventory",
    "docs/impl/workloads/two-source-pilot/inventory.yaml": "declaration/source-inventory",
    "docs/impl/workloads/two-source-pilot/link-decisions.yaml": "declaration/link-decisions",
    "docs/impl/workloads/two-source-pilot/plan-diverse.yaml": "declaration/discovery-plan",
    "docs/impl/workloads/two-source-pilot/plan-uniform.yaml": "declaration/discovery-plan",
    "docs/impl/workloads/two-source-pilot/pool.yaml": "declaration/corpus-pool",
    "docs/impl/workloads/two-source-pilot/reviews/pilot-diverse-grouped-20261113.yaml": (
        "declaration/corpus-review"
    ),
    "docs/impl/workloads/two-source-pilot/reviews/pilot-uniform-grouped-20261113.yaml": (
        "declaration/corpus-review"
    ),
    "scenarios/packs/aerial-small-objects.yaml": "declaration/scenario-pack",
}


def test_every_retained_input_is_held_to_a_contract() -> None:
    found = {
        str(path.relative_to(PROJECT_ROOT))
        for folder in RETAINED_FOLDERS
        for pattern in ("*.yaml", "*.yml")
        for path in (PROJECT_ROOT / folder).rglob(pattern)
    }
    assert found == set(RETAINED)


@pytest.mark.parametrize(("relative", "name"), sorted(RETAINED.items()))
def test_a_retained_input_validates_under_its_installed_contract(relative: str, name: str) -> None:
    newest = installed_contracts().contracts.named(name).newest()
    assert newest is not None and name.startswith("declaration/")
    read_declaration(PROJECT_ROOT / relative, name, newest.major)
