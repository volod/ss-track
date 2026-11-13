"""The controlling terminal of an interactive review, apart from the one JSON result line."""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

from ss_track.core.refusal import CorpusRefusal, RefusalCode


@contextmanager
def controlling_terminal(purpose: str) -> Iterator[tuple[TextIO, TextIO]]:
    """Yield the controlling terminal's input and output, or standard streams on a terminal.

    The command's JSON result still goes to its log, so the interaction never mixes with it.
    """
    try:
        descriptor = os.open("/dev/tty", os.O_RDWR)
    except OSError as error:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise CorpusRefusal(
                RefusalCode.WORKER_FAILED, f"{purpose} needs an interactive terminal"
            ) from error
        yield sys.stdin, sys.stdout
        return
    with (
        os.fdopen(os.dup(descriptor), "r", encoding="utf-8") as source,
        os.fdopen(descriptor, "w", encoding="utf-8", buffering=1) as output,
    ):
        yield source, output
