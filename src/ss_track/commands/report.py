"""How every command reports: one JSON record for its result or its refusal, and an exit status."""

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from ss_track.core.paths import resolve_data_root
from ss_track.core.refusal import CorpusRefusal, RefusalCode

EXIT_OK = 0
EXIT_REFUSED = 1

_LOG = logging.getLogger(__name__)


class Reportable(Protocol):
    """A command result, which states itself as one JSON-compatible record."""

    def to_record(self) -> Mapping[str, object]: ...


def log_json(level: int, record: dict[str, object]) -> None:
    """Log one record as sorted JSON, the one line a command prints."""
    _LOG.log(level, "%s", json.dumps(record, sort_keys=True))


def reported(action: Callable[[], Reportable]) -> int:
    """Run one action and report one JSON record for its result or its refusal."""
    try:
        result = action()
    except CorpusRefusal as refusal:
        return _refuse(refusal)
    except OSError as error:
        return _refuse(CorpusRefusal(RefusalCode.STORAGE_FAILED, f"storage failed: {error}"))
    except KeyboardInterrupt:
        return _refuse(CorpusRefusal(RefusalCode.INTERRUPTED, "interrupted by SIGINT"))
    log_json(logging.INFO, dict(result.to_record()))
    return EXIT_OK


def reported_on_data_root(action: Callable[[Path], Reportable]) -> int:
    """Run one action on the data root and report its one JSON record."""
    return reported(lambda: action(resolve_data_root()))


def _refuse(refusal: CorpusRefusal) -> int:
    """Log one refusal. A second SIGINT while that line is written still exits refused."""
    try:
        log_json(logging.ERROR, dict(refusal.to_record()))
    except KeyboardInterrupt:
        return EXIT_REFUSED
    return EXIT_REFUSED
