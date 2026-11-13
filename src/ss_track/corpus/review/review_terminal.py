"""What the audit and selection-pass terminal reviews share: prompts, effort and navigation."""

import math
from collections.abc import Callable
from typing import TextIO

IDLE_CAP_SECONDS = 300.0  # a longer pause between two actions counts as this much review work
SECONDS_PER_MINUTE = 60
OBSERVATIONS = {
    "t": "target_present",
    "a": "target_absent",
    "f": "confuser",
    "u": "unknown",
}
LOOK_HELP = """Look:    v play the frames as a loop; d play frame differences (moving objects light up);
         o open the frames folder in your image viewer to zoom. Close the player to return.
"""
MOVE_HELP = """Move:    n next; p previous; g next unreviewed; j jump to number; s summary; h help;
         q save and quit.
"""


def whole_minutes(seconds: float) -> int:
    """Whole minutes of recorded work, rounded up so that recorded work is never zero."""
    return math.ceil(seconds / SECONDS_PER_MINUTE)


class ReviewTerminal:
    """Prompts on injected streams; the time between two answers is charged as review work."""

    def __init__(
        self,
        streams: tuple[TextIO, TextIO],
        clock: Callable[[], float],
        charge: Callable[[float], None],
    ) -> None:
        self.source, self.output = streams
        self.clock, self.charge = clock, charge
        self.last = clock()

    def say(self, text: str) -> None:
        self.output.write(text)
        self.output.flush()

    def ask(self, prompt: str) -> str | None:
        """Return the stripped answer, or None at end of input."""
        self.say(prompt)
        line = self.source.readline()
        now = self.clock()
        self.charge(min(max(now - self.last, 0.0), IDLE_CAP_SECONDS))
        self.last = now
        return None if line == "" else line.strip()


def first_open(decided: Callable[[int], bool], size: int, start: int = 0) -> int | None:
    """Return the first undecided position at or after `start`, wrapping, or None."""
    for step in range(size):
        index = (start + step) % size
        if not decided(index):
            return index
    return None


def move(
    terminal: ReviewTerminal, action: str, index: int, size: int, decided: Callable[[int], bool]
) -> int:
    """Return the position after `n`, `p`, `g` or `j`."""
    if action == "n":
        return min(index + 1, size - 1)
    if action == "p":
        return max(index - 1, 0)
    if action == "g":
        found = first_open(decided, size, index + 1)
        if found is None:
            terminal.say("Every window is decided.\n")
        return index if found is None else found
    value = terminal.ask("Number: ")
    if value and value.isascii() and value.isdigit() and 1 <= int(value) <= size:
        return int(value) - 1
    terminal.say("Enter a number in the displayed range.\n")
    return index
