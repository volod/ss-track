"""How every command reports: one JSON record for its result or its refusal, and an exit status."""

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from ss_track.core.evidence.checked_roots import holds_path, one_command
from ss_track.core.evidence.contract_stamp import require_current_data_root
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
    """Run one action and report one JSON record for its result or its refusal.

    The action is one command, so its checks of an unstamped root may reuse a clean walk.
    """
    try:
        with one_command():
            result = action()
    except CorpusRefusal as refusal:
        return _refuse(refusal)
    except OSError as error:
        return _refuse(CorpusRefusal(RefusalCode.STORAGE_FAILED, f"storage failed: {error}"))
    except KeyboardInterrupt:
        return _refuse(CorpusRefusal(RefusalCode.INTERRUPTED, "interrupted by SIGINT"))
    log_json(logging.INFO, dict(result.to_record()))
    return EXIT_OK


def reported_on_data_root(
    action: Callable[[Path], Reportable], *, contracts_checked: bool = True
) -> int:
    """Run one action on the data root and report its one JSON record.

    The root is first held to the installed development contract set, so a record written under an
    earlier in-place contract edit is never read or extended. Only housekeeping that reads no
    record, such as `data clean`, passes `contracts_checked=False`.
    """
    return reported(
        lambda: action(checked_data_root() if contracts_checked else resolve_data_root())
    )


def checked_data_root() -> Path:
    """Return the data root once its records are known to follow the installed contracts."""
    data_root = resolve_data_root()
    require_current_data_root(data_root)
    return data_root


def check_root_holding(*outputs: Path) -> None:
    """Hold the data root to the installed contracts when an explicit output lands inside it.

    A command that takes its output paths instead of the data root still publishes data-root
    evidence when a path resolves under `DATA_DIR`, so the root is checked before any work and its
    sealed writes stamp it. An output outside the root stays standalone and the root is not read.
    """
    data_root = resolve_data_root()
    if any(holds_path(data_root, output) for output in outputs):
        require_current_data_root(data_root)


def _refuse(refusal: CorpusRefusal) -> int:
    """Log one refusal. A second SIGINT while that line is written still exits refused."""
    try:
        log_json(logging.ERROR, dict(refusal.to_record()))
    except KeyboardInterrupt:
        return EXIT_REFUSED
    return EXIT_REFUSED
