"""Where a staged stream's bundle sits, for the bundle-writer tests."""

from pathlib import Path

CORPUS = "pilot-v1"


def bundle_dir(data_root: Path, sequence: str = "one", corpus: str = CORPUS) -> Path:
    return data_root / "corpus" / corpus / "frames" / sequence
