"""Prepare the owner-selected hawk development workload from pinned public media."""

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from urllib.request import Request, urlopen

from ss_track.core.paths import resolve_data_root
from ss_track.quality.project_root import discover_project_root

SOURCE_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/Hawk_attacks_drone.webm"
SOURCE_SHA256 = "85534498c6a3422f13e17a02042e47ac3df414cbc8df58050a92bc62f3394e6c"
SOURCE_NAME = "hawk-attacks-drone.webm"
WORKLOAD_PATH = Path("workload-selection/hawk-drone-pilot")
TEMPLATE_PATH = Path("docs/impl/workloads/hawk-drone")
LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _download(destination: Path) -> None:
    request = Request(SOURCE_URL, headers={"User-Agent": "ss-track-workload/1.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def _ensure_source(directory: Path) -> Path:
    destination = directory / SOURCE_NAME
    if destination.exists():
        if _digest(destination) != SOURCE_SHA256:
            raise ValueError(f"Source hash mismatch; existing file kept: {destination}")
        return destination
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".download-", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        _download(temporary)
        if _digest(temporary) != SOURCE_SHA256:
            raise ValueError("Downloaded source hash mismatch; no source published")
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if _digest(destination) != SOURCE_SHA256:
                raise ValueError(
                    f"Source hash mismatch; existing file kept: {destination}"
                ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _ensure_template(source: Path, destination: Path) -> None:
    content = source.read_bytes()
    try:
        with destination.open("xb") as output:
            output.write(content)
    except FileExistsError:
        if destination.read_bytes() != content:
            raise ValueError(f"Declaration differs; existing file kept: {destination}") from None


def _ensure_sheet(source: Path, sheet: Path) -> None:
    if sheet.exists():
        return
    with tempfile.NamedTemporaryFile(dir=sheet.parent, suffix=".jpg", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-vf",
                "fps=1,scale=320:-1,tile=6x6",
                "-frames:v",
                "1",
                str(temporary),
            ],
            check=True,
        )
        with suppress(FileExistsError):
            os.link(temporary, sheet)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(data_root: Path, project_root: Path) -> Path:
    """Download the pinned video and create declarations without replacing existing files."""
    directory = data_root / WORKLOAD_PATH
    directory.mkdir(parents=True, exist_ok=True)
    source = _ensure_source(directory)
    for name in ("recording.yaml", "corpus.yaml"):
        _ensure_template(project_root / TEMPLATE_PATH / name, directory / name)
    _ensure_sheet(source, directory / "contact-sheet.jpg")
    return directory


def main() -> None:
    """Prepare the selected workload for a local checkout."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOGGER.info("Workload ready at %s", prepare(resolve_data_root(), discover_project_root()))


if __name__ == "__main__":
    main()
