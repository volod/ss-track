"""Regular expressions as values for the derivative proof.

Constructors keep union associative, commutative and idempotent, drop empty factors, and rewrite
a star of a star and `(r?){m,n}` when `r` cannot be empty. Those are the same language, and they
keep the later walk finite.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from ss_track.schema.compatibility.patterns import INFINITE, Atom, Part, Sequence

type Expr = _Void | _Epsilon | _Chars | _Alt | _Cat | _Rep


@dataclass(frozen=True, slots=True)
class _Void:
    pass


@dataclass(frozen=True, slots=True)
class _Epsilon:
    pass


@dataclass(frozen=True, slots=True)
class _Chars:
    values: frozenset[str]


@dataclass(frozen=True, slots=True)
class _Alt:
    items: frozenset[Expr]


@dataclass(frozen=True, slots=True)
class _Cat:
    items: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class _Rep:
    inner: Expr
    low: int
    high: int | None


ZERO = _Void()
ONE = _Epsilon()


def nullable(expr: Expr, cache: dict[Expr, bool] | None = None) -> bool:
    """Return whether `expr` admits the empty string."""
    if cache is not None and expr in cache:
        return cache[expr]
    result = _nullable(expr, cache)
    if cache is not None:
        cache[expr] = result
    return result


def _nullable(expr: Expr, cache: dict[Expr, bool] | None) -> bool:
    if isinstance(expr, _Epsilon):
        return True
    if isinstance(expr, _Void | _Chars):
        return False
    if isinstance(expr, _Alt):
        return any(nullable(item, cache) for item in expr.items)
    if isinstance(expr, _Cat):
        return all(nullable(item, cache) for item in expr.items)
    return expr.low == 0 or nullable(expr.inner, cache)


def alt(items: Iterable[Expr]) -> Expr:
    """Return the union of `items`, without the empty language and without duplicates."""
    found: set[Expr] = set()
    for item in items:
        if item == ZERO:
            continue
        if isinstance(item, _Alt):
            found.update(item.items)
        else:
            found.add(item)
    if not found:
        return ZERO
    if len(found) == 1:
        return next(iter(found))
    return _Alt(frozenset(found))


def cat(items: Iterable[Expr]) -> Expr:
    """Return the concatenation of `items`, without empty factors or adjacent copies of one star."""
    parts: list[Expr] = []
    for item in items:
        if item == ZERO:
            return ZERO
        if item == ONE:
            continue
        if isinstance(item, _Cat):
            parts.extend(item.items)
        else:
            parts.append(item)
    merged = _merge_stars(parts)
    if not merged:
        return ONE
    if len(merged) == 1:
        return merged[0]
    return _Cat(tuple(merged))


def _merge_stars(parts: list[Expr]) -> list[Expr]:
    merged: list[Expr] = []
    for item in parts:
        previous = merged[-1] if merged else None
        if isinstance(item, _Rep) and item == previous and item.low == 0 and item.high is None:
            continue
        merged.append(item)
    return merged


def repeat(inner: Expr, low: int, high: int | None) -> Expr:
    """Return `inner` repeated from `low` to `high` times; `None` means no upper bound."""
    if high == 0:
        return ONE
    if inner == ZERO:
        return ONE if low == 0 else ZERO
    if inner == ONE or (low, high) == (1, 1):
        return inner
    if isinstance(inner, _Rep) and inner.low == 0 and inner.high is None:
        return inner
    base = _optional(inner)
    if base is not None:
        return repeat(base, 0, high)
    return _Rep(inner, low, high)


def _optional(inner: Expr) -> Expr | None:
    """Return `r` when `inner` is `r?` and `r` cannot be empty, so `(r?){m,n}` is `r{0,n}`."""
    if not isinstance(inner, _Rep) or (inner.low, inner.high) != (0, 1):
        return None
    if nullable(inner.inner):
        return None
    return inner.inner


def compile_sequence(parts: Sequence) -> Expr:
    """Return the expression a parsed pattern denotes."""
    return cat(_part(part) for part in parts)


def _part(part: Part) -> Expr:
    high = None if part.high == INFINITE else int(part.high)
    return repeat(_atom(part.atom), part.low, high)


def _atom(atom: Atom) -> Expr:
    if isinstance(atom, frozenset):
        return _Chars(atom)
    return alt(compile_sequence(branch) for branch in atom)


def symbols(expr: Expr) -> set[frozenset[str]]:
    """Return every character class the expression names."""
    if isinstance(expr, _Chars):
        return {expr.values}
    if isinstance(expr, _Alt):
        return set().union(*(symbols(item) for item in expr.items))
    if isinstance(expr, _Cat):
        return set().union(*(symbols(item) for item in expr.items))
    if isinstance(expr, _Rep):
        return symbols(expr.inner)
    return set()
