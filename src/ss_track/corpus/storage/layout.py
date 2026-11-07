"""Where the data root keeps each record, each staged frame and each run.

Every path below the data root is composed here, so the writer and every reader of one record
name the same file, and a module that needs a path does not import the module that writes it.
"""

from pathlib import Path

IMPORT_DIRECTORY = "import"
CORPUS_DIRECTORY = "corpus"
FRAMES_DIRECTORY = "frames"
DESCRIPTIONS_DIRECTORY = "descriptions"
REPLACED_DIRECTORY = "replaced"
RUN_DIRECTORY = "run"
DISCOVERY_DIRECTORY = "self-supervised-corpus"
DISCOVERY_RUN_NAME = "run.json"
INVENTORIES_DIRECTORY = "inventories"
MANIFEST_NAME = "manifest.json"
FRAME_SET_NAME = "frame-set.json"
_REPLACED_SUFFIX = ".json"


def import_root(data_root: Path) -> Path:
    """Return the directory that holds every imported source."""
    return data_root / IMPORT_DIRECTORY


def source_directory(data_root: Path, source_sha256: str) -> Path:
    """Return the content-addressed home of one imported source."""
    return import_root(data_root) / source_sha256


def replaced_record_path(directory: Path, manifest_sha256: str) -> Path:
    """Return where a replaced source record is kept, under the seal corpus versions pinned."""
    return directory / REPLACED_DIRECTORY / f"{manifest_sha256}{_REPLACED_SUFFIX}"


def corpus_root(data_root: Path) -> Path:
    """Return the directory that holds every corpus version."""
    return data_root / CORPUS_DIRECTORY


def corpus_directory(data_root: Path, corpus_id: str) -> Path:
    """Return one corpus version's directory."""
    return corpus_root(data_root) / corpus_id


def corpus_manifest_path(data_root: Path, corpus_id: str) -> Path:
    """Return one corpus version's sealed manifest."""
    return corpus_directory(data_root, corpus_id) / MANIFEST_NAME


def frames_root(data_root: Path, corpus_id: str) -> Path:
    """Return the directory that holds every bundle of one corpus version."""
    return corpus_directory(data_root, corpus_id) / FRAMES_DIRECTORY


def frame_set_path(data_root: Path, corpus_id: str) -> Path:
    """Return a corpus version's frame set, beside its manifest."""
    return corpus_directory(data_root, corpus_id) / FRAME_SET_NAME


def descriptions_directory(data_root: Path, corpus_id: str) -> Path:
    """Return the directory that holds every published descriptor of one corpus version."""
    return corpus_directory(data_root, corpus_id) / DESCRIPTIONS_DIRECTORY


def run_root(data_root: Path) -> Path:
    """Return the directory that holds every run's records."""
    return data_root / RUN_DIRECTORY


def discovery_run_directory(data_root: Path, run_id: str) -> Path:
    """Return one discovery run's directory: its run record and one inventory per stream."""
    return data_root / DISCOVERY_DIRECTORY / run_id


def discovery_run_path(data_root: Path, run_id: str) -> Path:
    """Return one discovery run's sealed run record."""
    return discovery_run_directory(data_root, run_id) / DISCOVERY_RUN_NAME


def candidate_inventory_path(data_root: Path, run_id: str, stream_id: str) -> Path:
    """Return the sealed candidate inventory of one stream of a discovery run."""
    return discovery_run_directory(data_root, run_id) / INVENTORIES_DIRECTORY / f"{stream_id}.json"
