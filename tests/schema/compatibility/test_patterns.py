"""Pattern proofs, structural and derivative, checked against the independent automaton."""

import itertools
import json
import re
import time
from pathlib import Path

import pytest

from ss_track.schema.compatibility.change_rules import pattern_relaxed
from ss_track.schema.compatibility.derivatives import Decision, decide, matches
from ss_track.schema.compatibility.patterns import Sequence, covers, parse
from ss_track.schema.registry.store import default_root
from tests.schema.compatibility._automaton import Undecided, inclusion

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
    ("^ab$", "^[a-z]+$", False),  # structure misses it; derivatives prove the literal
    ("^(ab)*$", "^a*(ba)*b*$", False),
    ("^[0-9a-f]{64}$", "^[a-z0-9][a-z0-9._-]{0,63}$", True),
    ("^[0-9a-f]{64}$", "^[a-z0-9][a-z0-9._-]{0,62}$", False),
    ("^[ab]+$", "^a[ab]*$", False),
    ("^a+$", "^a[ab]*$", True),
]


@pytest.mark.parametrize(("old", "new", "proven"), PAIRS)
def test_structural_proof_is_sound_against_the_automaton(old: str, new: str, proven: bool) -> None:
    before, after = parse(old), parse(new)
    assert before is not None and after is not None
    assert covers(after, before) is proven
    found = inclusion(old, new)
    decision = decide(after, before)
    assert not decision.bounded
    assert decision.holds is found.holds
    assert pattern_relaxed(old, new) is found.holds
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


def test_a_literal_fits_a_pattern_outside_the_subset() -> None:
    assert pattern_relaxed("^ab$", "^a.$")
    assert not pattern_relaxed("^ab$", "^c$")


def _reshaped_pairs() -> list[tuple[str, str, bool]]:
    """Inclusions whose parts are not the structural proof's shape, plus near misses."""
    found = [
        (f"^({left}{right})*$", f"^{left}*({right}{left})*{right}*$", True)
        for left, right in itertools.permutations("abc", 2)
    ]
    found += [
        (f"^({left}{right})*$", f"^({right}{left})*$", False)
        for left, right in itertools.permutations("ab", 2)
    ]
    found += [(f"^{letter}+$", f"^{letter}*{letter}$", True) for letter in "ab"]
    found += [
        ("^[ab]{2}$", "^(a|b){2}$", True),
        ("^a*b*$", "^[ab]*$", True),
        ("^[ab]*$", "^a*b*$", False),
        ("^a?b?$", "^[ab]{0,2}$", True),
        ("^[ab]{0,2}$", "^a?b?$", False),
        ("^(ab){2,4}$", "^a*(ba)*b*$", True),
        ("^a*(ba)*b*$", "^(ab)*$", False),
    ]
    return found


def _generated_patterns() -> list[str]:
    atoms = ["a", "b", "[ab]", "(ab)", "(a|b)", "(a?b?)"]
    singles = [f"^{atom}$" for atom in atoms] + [f"^{atom}*$" for atom in atoms]
    singles += ["^$", "^(a*)*$", "^(a?b?){0,2}$", "^(a?b?){2}$", "^(a?){2,3}$", "^((a{0,2})?){2}$"]
    pairs = [f"^{left}{right}$" for left, right in itertools.product(["a", "b*", "[ab]"], repeat=2)]
    return singles + pairs


@pytest.mark.parametrize(("old", "new", "holds"), _reshaped_pairs())
def test_reshaped_inclusion_is_minor_exactly_when_it_holds(old: str, new: str, holds: bool) -> None:
    before, after = parse(old), parse(new)
    assert before is not None and after is not None
    if holds:
        assert not covers(after, before)
    decision = decide(after, before)
    assert decision == Decision(holds, decision.states, False)
    assert pattern_relaxed(old, new) is holds
    assert inclusion(old, new).holds is holds


def test_derivatives_admit_each_short_string_re_admits() -> None:
    patterns = _generated_patterns() + [item for pair in _reshaped_pairs() for item in pair[:2]]
    for pattern in sorted(set(patterns)):
        parts = parse(pattern)
        assert parts is not None
        for size in range(5):
            for chars in itertools.product("abc", repeat=size):
                text = "".join(chars)
                assert matches(parts, text) is (re.fullmatch(pattern, text) is not None), (
                    pattern,
                    text,
                )


def test_generated_patterns_agree_with_the_automaton() -> None:
    patterns = _generated_patterns()
    for old, new in itertools.product(patterns, repeat=2):
        before, after = parse(old), parse(new)
        assert before is not None and after is not None
        decision = decide(after, before)
        assert not decision.bounded, (old, new, decision.states)
        assert decision.holds is inclusion(old, new).holds, (old, new)


def test_an_unfinished_walk_does_not_relax_a_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    def stopped(new: Sequence, old: Sequence) -> Decision:
        return decide(new, old, limit=1)

    monkeypatch.setattr("ss_track.schema.compatibility.change_rules.decide", stopped)
    old, new = "^(ab)*$", "^a*(ba)*b*$"
    assert not pattern_relaxed(old, new)
    before, after = parse(old), parse(new)
    assert before is not None and after is not None
    assert decide(after, before).holds


def test_derivative_walks_on_the_measured_tables_stay_cheap() -> None:
    contract = _contract_patterns()
    started = time.perf_counter()
    for old, new in itertools.product(contract, repeat=2):
        before, after = parse(old), parse(new)
        assert before is not None and after is not None
        if covers(after, before):
            continue
        assert not decide(after, before).bounded
    for old, new, _holds in _reshaped_pairs():
        before, after = parse(old), parse(new)
        assert before is not None and after is not None
        assert not decide(after, before).bounded
    assert time.perf_counter() - started < 1


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
