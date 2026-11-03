"""The classifier's structural pattern proof, checked against the independent automaton."""

import itertools
import json
from pathlib import Path

import pytest

from ss_track.schema._change_rules import pattern_relaxed
from ss_track.schema._patterns import parse
from ss_track.schema.store import default_root
from tests.schema._automaton import Undecided, inclusion

# old, new, structurally proven
PAIRS = [
    ("^[ab]+$", "^[abc]+$", True),
    ("^[abc]+$", "^[ab]+$", False),
    ("^[ab]{2,3}$", "^[a-c]{1,}$", True),
    ("^[ab]{1,}$", "^[ab]{2,3}$", False),
    ("^(ab)+$", "^(ab|cd)+$", True),
    ("^(?:ab|cd)+$", "^(ab)+$", False),
    ("^[a-z0-9]+(-[a-z0-9]+)*$", "^[a-z0-9_]+(-[a-z0-9_]+)*$", True),
    ("^[a-z0-9][a-z0-9._-]{0,62}$", "^[a-z0-9][a-z0-9._-]{0,63}$", True),
    ("^[a-z0-9][a-z0-9._-]{0,63}$", "^[a-z0-9][a-z0-9._-]{0,62}$", False),
    ("^[0-9]+/[1-9][0-9]*$", "^-?[0-9]+/[1-9][0-9]*$", True),
    ("^-?[0-9]+/[1-9][0-9]*$", "^[0-9]+/[1-9][0-9]*$", False),
    ("^a$", "^a(b)?$", True),
    ("^abc$", "^a?b?$", False),
    ("^\\$$", "^[$]$", True),
    ("^ab$", "^[a-z]+$", True),
    ("^(ab)*$", "^a*(ba)*b*$", False),
    ("^[0-9a-f]{64}$", "^[a-z0-9][a-z0-9._-]{0,63}$", True),
    ("^[0-9a-f]{64}$", "^[a-z0-9][a-z0-9._-]{0,62}$", False),
    ("^[ab]+$", "^a[ab]*$", False),
    ("^a+$", "^a[ab]*$", True),
]


@pytest.mark.parametrize(("old", "new", "proven"), PAIRS)
def test_structural_proof_is_sound_against_the_automaton(old: str, new: str, proven: bool) -> None:
    assert pattern_relaxed(old, new) is proven
    found = inclusion(old, new)
    if proven:
        assert found.holds
    if not found.holds:
        assert found.witness is not None and not pattern_relaxed(old, new)


@pytest.mark.parametrize(
    "pattern",
    [
        "^.$",
        "^[^a]$",
        "^[]a]$",
        "^\\d$",
        "^(?=a)a$",
        "^a|b$",
        "a+$",
        "^a+",
        "^a**$",
        "^a{3,2}$",
        "^é$",
        "^[b-a]$",
        "^(a$",
    ],
)
def test_syntax_outside_the_subset_is_unproven_by_both(pattern: str) -> None:
    assert parse(pattern) is None
    with pytest.raises(Undecided):
        inclusion(pattern, pattern)
    assert not pattern_relaxed(pattern, pattern + "x")


def _contract_patterns() -> list[str]:
    found: set[str] = set()

    def visit(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("pattern"), str):
                found.add(node["pattern"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    for path in Path(default_root()).rglob("*.json"):
        if "meta" not in path.parts:
            visit(json.loads(path.read_text(encoding="utf-8")))
    return sorted(found)


def test_on_contract_patterns_the_classifier_proves_exactly_what_holds() -> None:
    patterns = _contract_patterns()
    assert patterns and all(parse(pattern) is not None for pattern in patterns)
    for old, new in itertools.product(patterns, repeat=2):
        assert pattern_relaxed(old, new) is inclusion(old, new).holds, (old, new)
