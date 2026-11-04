"""The fixed corpus two architectures stage, and the commands that write and stage it.

Sources are written once and carried to the other host. Writing media again gives other bytes, on
one host through a container's random identifiers and across architectures in the packets too, so a
host that regenerated them would compare different sources. No binary enters the repository:
`write` keeps the media of the `_fixed_sources` table under a run directory, and the CI workflow
moves it between jobs.
"""

import argparse
import logging
from pathlib import Path

import yaml

from ss_track.core.paths import resolve_data_root
from ss_track.corpus import build_corpus, import_source, record_staged_hashes, stage_corpus
from tests.corpus._media import write_clip
from tests.corpus.conftest import case_of, corpus_declaration, group_of, recording_declaration
from tests.corpus.hosts._fixed_sources import (
    CASE_PARENT,
    CASES,
    SOURCES,
    FixedSource,
    source_content,
)

CORPUS_ID = "arch-fixed-v1"
CORPUS_FILE = "corpus.yaml"
RECORDINGS_FILE = "recordings.yaml"
_WINDOW = {"start_frame": 3, "end_frame": 9}
_LOG = logging.getLogger(__name__)


def _recording_name(source: FixedSource) -> str:
    return f"{source.name}.yaml"


def write_sources(output: Path, sources: tuple[FixedSource, ...] = SOURCES) -> Path:
    """Write every source and its recording declaration into one directory that can be moved."""
    output.mkdir(parents=True, exist_ok=True)
    for source in sources:
        write_clip(
            output / source.file_name,
            source.codec,
            source.pixel_format,
            source.options,
            frames=source.frames,
            width=source.width,
            height=source.height,
            content=source_content(source.name),
        )
        declaration = yaml.safe_dump(recording_declaration(source.file_name))
        (output / _recording_name(source)).write_text(declaration, encoding="utf-8")
    names = [_recording_name(source) for source in sources]
    (output / RECORDINGS_FILE).write_text(yaml.safe_dump(names), encoding="utf-8")
    return output


def _stream(name: str, source_sha256: str) -> dict[str, object]:
    stream: dict[str, object] = {"stream_id": name, "source_sha256": source_sha256}
    if name == CASE_PARENT:
        stream["generated_cases"] = [
            case_of(f"{name}-{transform}", transform, seed, parameters, window=_WINDOW)
            for seed, (transform, parameters) in enumerate(CASES)
        ]
    return stream


def _write_corpus(sources: Path, source_hashes: dict[str, str]) -> Path:
    """Declare one group of one encounter per source, which holds every transform once."""
    encounters = [
        {"encounter_id": name, "streams": [_stream(name, sha256)]}
        for name, sha256 in sorted(source_hashes.items())
    ]
    declaration = corpus_declaration(
        [group_of("fixed", "development", *encounters)], corpus_id=CORPUS_ID
    )
    path = sources / CORPUS_FILE
    path.write_text(yaml.safe_dump(declaration), encoding="utf-8")
    return path


def stage_sources(sources: Path, run_id: str, data_root: Path) -> str:
    """Import, build, stage and verify the corpus, record its hashes, and return its frame set."""
    names = yaml.safe_load((sources / RECORDINGS_FILE).read_text(encoding="utf-8"))
    hashes = {
        Path(name).stem: import_source(sources / name, data_root).source_sha256 for name in names
    }
    build_corpus(_write_corpus(sources, hashes), data_root)
    stage_corpus(CORPUS_ID, data_root)
    return record_staged_hashes(CORPUS_ID, run_id, data_root).frame_set_sha256


def main() -> None:
    """Write the sources, or stage ones that another host wrote."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", help="write the sources once")
    write.add_argument("--output", type=Path, required=True)
    stage = commands.add_parser("stage", help="stage stored sources and record their hashes")
    stage.add_argument("--sources", type=Path, required=True)
    stage.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "write":
        _LOG.info("wrote %d sources to %s", len(SOURCES), write_sources(args.output))
    else:
        frame_set = stage_sources(args.sources, args.run_id, resolve_data_root())
        _LOG.info("frame_set_sha256 %s", frame_set)


if __name__ == "__main__":
    main()
