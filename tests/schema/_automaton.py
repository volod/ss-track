"""Decide inclusion between two anchored patterns with automata, independent of the classifier.

Each pattern becomes a Thompson automaton, and a breadth-first walk of both at once either exhausts
every state pair, proving inclusion, or reaches a string the old pattern accepts and the new one
refuses: the shortest such string is the witness. `_pattern_reader` states the syntax decided.
"""

from collections import deque
from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass, field
from typing import Any

from tests.schema._pattern_reader import Node, Undecided, read

__all__ = ["Inclusion", "Undecided", "automaton", "inclusion", "shortest"]

MAX_STATES = 20_000
MAX_PAIRS = 200_000


@dataclass(frozen=True, slots=True)
class Inclusion:
    """`holds` is the verdict; `witness` is the shortest old-only string when it fails."""

    holds: bool
    witness: str | None = None


@dataclass
class _Automaton:
    moves: list[list[tuple[frozenset[str], int]]] = field(default_factory=list)
    empty: list[list[int]] = field(default_factory=list)

    def state(self) -> int:
        if len(self.moves) >= MAX_STATES:
            raise Undecided("automaton too large")
        self.moves.append([])
        self.empty.append([])
        return len(self.moves) - 1

    def link(self, source: int, target: int) -> None:
        self.empty[source].append(target)

    def closure(self, states: set[int]) -> frozenset[int]:
        found, pending = set(states), list(states)
        while pending:
            for target in self.empty[pending.pop()]:
                if target not in found:
                    found.add(target)
                    pending.append(target)
        return frozenset(found)

    def step(self, states: frozenset[int], character: str) -> frozenset[int]:
        reached = {
            target
            for state in states
            for characters, target in self.moves[state]
            if character in characters
        }
        return self.closure(reached)


type Pair = tuple[frozenset[int], frozenset[int]]
type Step = Callable[[Any], Iterator[tuple[str, Any]]]


def _build(nfa: _Automaton, node: Node) -> tuple[int, int]:
    """Return the entry and exit states of a fresh fragment for one node."""
    entry = nfa.state()
    match node:
        case ("set", characters):
            exit_ = nfa.state()
            nfa.moves[entry].append((characters, exit_))
            return entry, exit_
        case ("cat", items):
            current = entry
            for item in items:
                start, current_exit = _build(nfa, item)
                nfa.link(current, start)
                current = current_exit
            return entry, current
        case ("alt", branches):
            exit_ = nfa.state()
            for branch in branches:
                start, end = _build(nfa, branch)
                nfa.link(entry, start)
                nfa.link(end, exit_)
            return entry, exit_
    _, inner, low, high = node
    return entry, _repeat(nfa, entry, inner, low, high)


def _repeat(nfa: _Automaton, current: int, inner: Node, low: int, high: int | None) -> int:
    for _ in range(low):
        start, end = _build(nfa, inner)
        nfa.link(current, start)
        current = end
    if high is None:
        start, end = _build(nfa, inner)
        nfa.link(current, start)
        nfa.link(end, current)
        return current
    done = nfa.state()
    for _ in range(high - low):
        start, end = _build(nfa, inner)
        nfa.link(current, done)
        nfa.link(current, start)
        current = end
    nfa.link(current, done)
    return done


def automaton(pattern: str) -> tuple[_Automaton, int, int]:
    """Return an automaton accepting exactly the strings an anchored pattern matches."""
    nfa = _Automaton()
    entry, exit_ = _build(nfa, read(pattern))
    return nfa, entry, exit_


def _first(start: Hashable, step: Step, done: Callable[[Any], bool]) -> str | None:
    """Return the shortest, then first, text whose walk from `start` reaches a `done` state."""
    seen, queue = {start}, deque([(start, "")])
    while queue:
        state, text = queue.popleft()
        if done(state):
            return text
        for character, following in step(state):
            if following not in seen:
                if len(seen) >= MAX_PAIRS:
                    raise Undecided("state search exceeds its bound")
                seen.add(following)
                queue.append((following, text + character))
    return None


def _alphabet(nfa: _Automaton) -> list[str]:
    return sorted(set().union(*(chars for row in nfa.moves for chars, _ in row)))


def inclusion(old: str, new: str) -> Inclusion:
    """Decide whether every string `old` matches is matched by `new`; raise `Undecided` if not."""
    left, left_start, left_accept = automaton(old)
    right, right_start, right_accept = automaton(new)
    alphabet = _alphabet(left)

    def step(pair: Pair) -> Iterator[tuple[str, Pair]]:
        for character in alphabet:
            before = left.step(pair[0], character)
            if before:
                yield character, (before, right.step(pair[1], character))

    start = (left.closure({left_start}), right.closure({right_start}))
    witness = _first(
        start, step, lambda pair: left_accept in pair[0] and right_accept not in pair[1]
    )
    return Inclusion(witness is None, witness)


def shortest(pattern: str, min_length: int = 0) -> str:
    """Return the shortest, then first, string of at least `min_length` the pattern matches."""
    nfa, entry, accept = automaton(pattern)
    alphabet = _alphabet(nfa)

    def step(state: tuple[frozenset[int], int]) -> Iterator[tuple[str, Any]]:
        for character in alphabet:
            following = nfa.step(state[0], character)
            if following:
                yield character, (following, min(state[1] + 1, min_length))

    found = _first(
        (nfa.closure({entry}), 0), step, lambda state: accept in state[0] and state[1] >= min_length
    )
    if found is None:
        raise Undecided(f"no string of length {min_length} or more matches {pattern}")
    return found
