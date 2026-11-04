"""Decide pattern inclusion by Brzozowski derivatives.

The structural proof sees one shape. This walk treats two patterns as languages: each character
takes a derivative, and inclusion fails where the old language can end and the new one cannot.
It shares no code with the test automaton. Past its state bound the relationship is unproven.
"""

from collections import deque
from dataclasses import dataclass

from ss_track.schema._derivative_expr import (
    ONE,
    ZERO,
    Expr,
    _Cat,
    _Chars,
    _Epsilon,
    _Rep,
    _Void,
    alt,
    cat,
    compile_sequence,
    nullable,
    repeat,
    symbols,
)
from ss_track.schema._patterns import Sequence

MAX_STATES = 8_192


@dataclass(frozen=True, slots=True)
class Decision:
    """`holds` is proven inclusion; `bounded` means the walk stopped before deciding."""

    holds: bool
    states: int
    bounded: bool


class _Walker:
    def __init__(self) -> None:
        self._null: dict[Expr, bool] = {}
        self._derived: dict[tuple[Expr, str], Expr] = {}

    def empty(self, expr: Expr) -> bool:
        return nullable(expr, self._null)

    def derive(self, expr: Expr, char: str) -> Expr:
        key = (expr, char)
        if key not in self._derived:
            self._derived[key] = self._derive(expr, char)
        return self._derived[key]

    def _derive(self, expr: Expr, char: str) -> Expr:
        if isinstance(expr, _Void | _Epsilon):
            return ZERO
        if isinstance(expr, _Chars):
            return ONE if char in expr.values else ZERO
        if isinstance(expr, _Cat):
            return self._derive_cat(expr, char)
        if isinstance(expr, _Rep):
            return self._derive_rep(expr, char)
        return alt(self.derive(item, char) for item in expr.items)

    def _derive_cat(self, expr: _Cat, char: str) -> Expr:
        head, *tail = expr.items
        rest = cat(tail)
        found = [cat((self.derive(head, char), rest))]
        if self.empty(head):
            found.append(self.derive(rest, char))
        return alt(found)

    def _derive_rep(self, expr: _Rep, char: str) -> Expr:
        if expr.low == 0 and expr.high is None:
            return cat((self.derive(expr.inner, char), expr))
        if expr.low == 0 and expr.high is not None:
            return self._derive_optional(expr.inner, expr.high, char)
        return self._derive_counted(expr, char)

    def _derive_counted(self, expr: _Rep, char: str) -> Expr:
        next_high = None if expr.high is None else expr.high - 1
        continued = repeat(expr.inner, expr.low - 1, next_high)
        taken = cat((self.derive(expr.inner, char), continued))
        if self.empty(expr.inner):
            return alt((taken, self.derive(continued, char)))
        return taken

    def _derive_optional(self, inner: Expr, high: int, char: str) -> Expr:
        if high == 0:
            return ZERO
        if not self.empty(inner):
            return cat((self.derive(inner, char), repeat(inner, 0, high - 1)))
        current = self.derive(inner, char)
        for count in range(2, high + 1):
            rest = repeat(inner, 0, count - 1)
            current = alt((cat((self.derive(inner, char), rest)), current))
        return current


def _representatives(left: Expr, right: Expr) -> tuple[str, ...]:
    classes = list(symbols(left) | symbols(right))
    if not classes:
        return ()
    groups: dict[tuple[bool, ...], str] = {}
    for char in set().union(*classes):
        groups.setdefault(tuple(char in item for item in classes), char)
    return tuple(sorted(groups.values()))


def _search(walk: _Walker, start: tuple[Expr, Expr], limit: int) -> Decision:
    chars = _representatives(*start)
    seen = {start}
    pending = deque([start])
    while pending:
        before, after = pending.popleft()
        if before in (ZERO, after):
            continue
        if walk.empty(before) and not walk.empty(after):
            return Decision(False, len(seen), False)
        if not _enqueue(walk, before, after, chars, seen, pending, limit):
            return Decision(False, len(seen), True)
    return Decision(True, len(seen), False)


def _enqueue(
    walk: _Walker,
    before: Expr,
    after: Expr,
    chars: tuple[str, ...],
    seen: set[tuple[Expr, Expr]],
    pending: deque[tuple[Expr, Expr]],
    limit: int,
) -> bool:
    for char in chars:
        following = (walk.derive(before, char), walk.derive(after, char))
        if following in seen:
            continue
        if len(seen) >= limit:
            return False
        seen.add(following)
        pending.append(following)
    return True


def decide(new: Sequence, old: Sequence, *, limit: int = MAX_STATES) -> Decision:
    """Return whether `new` admits every string `old` does.

    `holds` is false both for a counterexample and for a walk that passes `limit`. Only a finished
    walk that finds no counterexample proves inclusion.
    """
    walk = _Walker()
    return _search(walk, (compile_sequence(old), compile_sequence(new)), limit)


def matches(parts: Sequence, text: str) -> bool:
    """Return whether the pattern admits `text`, by the same derivatives as `decide`."""
    walk = _Walker()
    expr = compile_sequence(parts)
    for char in text:
        expr = walk.derive(expr, char)
    return walk.empty(expr)
