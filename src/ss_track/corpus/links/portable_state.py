"""Paths and checkpoint identities shared by portable review export and acceptance."""

from pathlib import Path

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.links.interactive_state import CHECKPOINT_NAME
from ss_track.corpus.records.kinds import LINK_REVIEW_HANDOFF
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.storage.layout import discovery_run_directory

STATE_DIRECTORY = "portable-review"
ACCEPTED_NAME = "accepted-handoff.json"


def checkpoint_path(data_root: Path, run_id: str) -> Path:
    """Return the interactive checkpoint of one link run."""
    return discovery_run_directory(data_root, run_id) / "link-review" / CHECKPOINT_NAME


def accepted_path(data_root: Path, run_id: str) -> Path:
    """Return the last handoff this host accepted for one link run."""
    return discovery_run_directory(data_root, run_id) / STATE_DIRECTORY / ACCEPTED_NAME


def file_digest(path: Path) -> str | None:
    """Hash a regular optional checkpoint, refusing a symbolic one."""
    if path.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "review checkpoint is a symbolic link")
    return sha256_bytes(path.read_bytes()) if path.is_file() else None


def base_checkpoint(data_root: Path, run_id: str, current: str | None) -> str | None:
    """Return the checkpoint branch point retained from the last accepted handoff."""
    accepted = accepted_path(data_root, run_id)
    if not accepted.exists():
        return current
    record = read_sealed(accepted, LINK_REVIEW_HANDOFF)
    value = record["checkpoint_sha256"]
    return None if value is None else str(value)
