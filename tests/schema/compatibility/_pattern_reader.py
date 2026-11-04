"""Read an anchored pattern into nodes, for the automaton oracle and nothing else.

Only ASCII literals, escapes, positive classes, groups, alternation and quantifiers are read,
because there `re` and ECMA-262 agree. `.` and negated classes differ at line terminators and
astral characters, so reading them raises `Undecided`.
"""

import re

_META = set(".^$|?*+()[]{}\\")
_IN_CLASS = set("[]\\")  # `[` may open a nested set in a future `re`.
_ESCAPABLE = set(".^$|?*+()[]{}\\/-")
_CONTROL = {"n": "\n", "r": "\r", "t": "\t"}
_COUNT = re.compile(r"\{([0-9]+)(?:(,)([0-9]*))?\}")


class Undecided(Exception):
    """The pattern falls outside the decided subset, or the search exceeds its bound."""


type Node = tuple[object, ...]


class _Reader:
    """Read a pattern into nodes: `("set", chars)`, `("cat", nodes)`, `("alt", nodes)`, `("rep",
    node, low, high)`, with `None` for no upper bound."""

    def __init__(self, text: str) -> None:
        self.text, self.at = text, 0

    def peek(self) -> str:
        return self.text[self.at : self.at + 1]

    def take(self) -> str:
        if not self.peek():
            raise Undecided("unexpected end")
        self.at += 1
        return self.text[self.at - 1]

    def choice(self) -> list[Node]:
        branches = [self.sequence()]
        while self.peek() == "|":
            self.at += 1
            branches.append(self.sequence())
        return branches

    def sequence(self) -> Node:
        items = []
        while self.peek() not in ("", "|", ")", "$"):
            items.append(self.repeat(self.atom()))
        return ("cat", items)

    def atom(self) -> Node:
        character = self.take()
        if character == "(":
            if self.text.startswith("?:", self.at):
                self.at += 2
            branches = self.choice()
            if self.take() != ")":
                raise Undecided("unclosed group")
            return ("alt", branches)
        if character == "[":
            return ("set", self.characters())
        return ("set", frozenset(self.escape() if character == "\\" else _plain(character)))

    def repeat(self, node: Node) -> Node:
        character = self.peek()
        if character in ("*", "+", "?"):
            self.at += 1
            low, high = {"*": (0, None), "+": (1, None), "?": (0, 1)}[character]
        elif character == "{":
            match = _COUNT.match(self.text, self.at)
            if match is None:
                raise Undecided("malformed count")
            self.at = match.end()
            low = int(match[1])
            high = low if match[2] is None else int(match[3]) if match[3] else None
            if high is not None and high < low:
                raise Undecided("descending count")
        else:
            return node
        if self.peek() == "?":
            self.at += 1  # A lazy quantifier matches the same strings.
        if self.peek() in ("*", "+", "?", "{"):
            raise Undecided("stacked quantifier")
        return ("rep", node, low, high)

    def characters(self) -> frozenset[str]:
        if self.peek() in ("^", "]"):
            raise Undecided("negated or empty class")
        found: set[str] = set()
        while (character := self.take()) != "]":
            low = self.member(character)
            if self.peek() == "-" and self.text[self.at + 1 : self.at + 2] != "]":
                self.at += 1
                high = self.member(self.take())
                if high < low:
                    raise Undecided("descending range")
                found.update(chr(code) for code in range(ord(low), ord(high) + 1))
            else:
                found.add(low)
        return frozenset(found)

    def member(self, character: str) -> str:
        return self.escape() if character == "\\" else _plain(character, _IN_CLASS)

    def escape(self) -> str:
        character = self.take()
        if character in _ESCAPABLE:
            return character
        if character in _CONTROL:
            return _CONTROL[character]
        raise Undecided(f"escape \\{character}")


def _plain(character: str, special: set[str] = _META) -> str:
    if not " " <= character <= "~" or character in special:
        raise Undecided(f"character {character!r}")
    return character


def read(pattern: str) -> Node:
    """Return the node of a pattern anchored at both ends, or raise `Undecided`."""
    reader = _Reader(pattern)
    if reader.take() != "^":
        raise Undecided("pattern is not anchored at the start")
    branches = reader.choice()
    if len(branches) != 1:
        raise Undecided("top-level alternation binds the anchors to separate branches")
    if reader.take() != "$" or reader.peek():
        raise Undecided("pattern is not anchored at the end")
    return branches[0]
