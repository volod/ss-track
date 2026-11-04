"""Prove that one anchored pattern admits every string another admits, by matching structure.

The proof is syntactic and sound: the new pattern must have the old one's sequence of parts, plus
any parts that may occur zero times, and each new part must admit every string its old counterpart
does; an old repetition may first give up one occurrence. A class covers a smaller class, a repetition
covers a narrower count, and a group covers every old alternative with some new one. The supported
syntax is the ASCII core every engine reads alike: literals, escapes, positive classes, groups,
alternation and greedy or lazy quantifiers. Anything else is unproven. A true inclusion whose shape
changed is decided apart from this reading, in `_derivatives`.
"""

import re
from dataclasses import dataclass

INFINITE = float("inf")
_META = set(".^$|?*+()[]{}\\")
_IN_CLASS = set("[]\\")  # `[` may open a nested set in a future `re`.
_ESCAPABLE = set(".^$|?*+()[]{}\\/-")
_CONTROL = {"n": "\n", "r": "\r", "t": "\t"}
_PRINTABLE = (" ", "~")
_QUANTIFIERS = {"*": (0, INFINITE), "+": (1, INFINITE), "?": (0, 1)}
_COUNT = re.compile(r"\{([0-9]+)(?:(,)([0-9]*))?\}")

type Atom = frozenset[str] | tuple[Sequence, ...]
type Sequence = tuple[Part, ...]


@dataclass(frozen=True, slots=True)
class Part:
    """One atom repeated between `low` and `high` times."""

    atom: Atom
    low: int
    high: float


class _Unsupported(Exception):
    """The pattern uses syntax outside the proven subset."""


class _Parser:
    def __init__(self, text: str) -> None:
        self.text, self.position = text, 0

    def peek(self) -> str:
        return self.text[self.position : self.position + 1]

    def take(self) -> str:
        character = self.peek()
        if not character:
            raise _Unsupported("unexpected end")
        self.position += 1
        return character

    def alternatives(self) -> tuple[Sequence, ...]:
        branches = [self.sequence()]
        while self.peek() == "|":
            self.position += 1
            branches.append(self.sequence())
        return tuple(branches)

    def sequence(self) -> Sequence:
        parts = []
        while self.peek() not in ("", "|", ")", "$"):
            parts.append(self.repeated(self.atom()))
        return tuple(parts)

    def atom(self) -> Atom:
        character = self.take()
        if character == "(":
            if self.text.startswith("?:", self.position):
                self.position += 2
            group = self.alternatives()
            if self.take() != ")":
                raise _Unsupported("unclosed group")
            return group
        if character == "[":
            return self.character_class()
        return frozenset(self.escape() if character == "\\" else _literal(character))

    def repeated(self, atom: Atom) -> Part:
        character = self.peek()
        if character in _QUANTIFIERS:
            self.position += 1
            low, high = _QUANTIFIERS[character]
        elif character == "{":
            low, high = self.count()
        else:
            return Part(atom, 1, 1)
        if self.peek() == "?":
            self.position += 1  # A lazy quantifier admits the same strings.
        if self.peek() in _QUANTIFIERS or self.peek() == "{":
            raise _Unsupported("stacked quantifier")
        return Part(atom, int(low), high)

    def count(self) -> tuple[int, float]:
        match = _COUNT.match(self.text, self.position)
        if match is None:
            raise _Unsupported("malformed count")
        self.position = match.end()
        low = int(match[1])
        high: float = low if match[2] is None else int(match[3]) if match[3] else INFINITE
        if high < low:
            raise _Unsupported("descending count")
        return low, high

    def character_class(self) -> frozenset[str]:
        if self.peek() in ("^", "]"):
            raise _Unsupported("negated or empty class")
        characters: set[str] = set()
        while (character := self.take()) != "]":
            low = self.member(character)
            if self.peek() == "-" and self.text[self.position + 1 : self.position + 2] != "]":
                self.position += 1
                high = self.member(self.take())
                if high < low:
                    raise _Unsupported("descending range")
                characters.update(chr(code) for code in range(ord(low), ord(high) + 1))
            else:
                characters.add(low)
        return frozenset(characters)

    def member(self, character: str) -> str:
        return self.escape() if character == "\\" else _literal(character, _IN_CLASS)

    def escape(self) -> str:
        character = self.take()
        if character in _ESCAPABLE:
            return character
        if character in _CONTROL:
            return _CONTROL[character]
        raise _Unsupported(f"escape \\{character}")


def _literal(character: str, special: set[str] = _META) -> str:
    if not _PRINTABLE[0] <= character <= _PRINTABLE[1] or character in special:
        raise _Unsupported(f"character {character!r}")
    return character


def parse(pattern: str) -> Sequence | None:
    """Return the parts of a pattern anchored at both ends, or nothing outside the subset."""
    parser = _Parser(pattern)
    try:
        if parser.take() != "^":
            return None
        branches = parser.alternatives()
        if len(branches) != 1 or parser.take() != "$" or parser.peek():
            return None
    except _Unsupported:
        return None
    return branches[0]


def _alternatives(atom: Atom) -> tuple[Sequence, ...]:
    return ((Part(atom, 1, 1),),) if isinstance(atom, frozenset) else atom


def _atom_covers(new: Atom, old: Atom) -> bool:
    if isinstance(new, frozenset) and isinstance(old, frozenset):
        return old <= new
    choices = _alternatives(new)
    return all(any(covers(choice, branch) for choice in choices) for branch in _alternatives(old))


def _part_covers(new: Part, old: Part) -> bool:
    return new.low <= old.low and old.high <= new.high and _atom_covers(new.atom, old.atom)


def _unrolled(old: Sequence) -> Sequence | None:
    """Return `c{m,n}` as `c` then `c{m-1,n-1}`, an equal language, when `m` is at least one."""
    if not old or old[0].low < 1 or old[0].high <= 1:
        return None
    head = old[0]
    return (Part(head.atom, 1, 1), Part(head.atom, head.low - 1, head.high - 1), *old[1:])


def covers(new: Sequence, old: Sequence) -> bool:
    """Say whether `new` admits every string `old` does, part by part.

    A new part that may repeat zero times may also stand against nothing, as `-?` does when it is
    added in front of a number. An old repetition may give one occurrence to a new single part, so
    a 64-character hash fits an identifier's first character and its remaining 63.
    """
    if not new:
        return not old
    head, rest = new[0], new[1:]
    if old and _part_covers(head, old[0]) and covers(rest, old[1:]):
        return True
    unrolled = _unrolled(old) if head.high == 1 else None
    if unrolled is not None and covers(new, unrolled):
        return True
    return head.low == 0 and covers(rest, old)
