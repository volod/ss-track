"""Command-line entrypoint for project diagnostics and corpus provenance."""

import argparse
import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from ss_track.corpus import (
    BuildResult,
    CorpusRefusal,
    FramesResult,
    ImportResult,
    RefusalCode,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus import build_corpus as run_corpus_build
from ss_track.corpus import import_source as run_import
from ss_track.metadata import project_info
from ss_track.paths import resolve_data_root

EXIT_OK = 0
EXIT_REFUSED = 1

_LOG = logging.getLogger(__name__)


def _log_json(level: int, record: dict[str, object]) -> None:
    _LOG.log(level, "%s", json.dumps(record, sort_keys=True))


def _refuse(refusal: CorpusRefusal) -> int:
    _log_json(logging.ERROR, dict(refusal.to_record()))
    return EXIT_REFUSED


def _report(action: Callable[[Path], ImportResult | BuildResult | FramesResult]) -> int:
    """Run one corpus action and report one JSON record for its result or its refusal."""
    try:
        result = action(resolve_data_root())
    except CorpusRefusal as refusal:
        return _refuse(refusal)
    except OSError as error:
        return _refuse(CorpusRefusal(RefusalCode.STORAGE_FAILED, f"storage failed: {error}"))
    _log_json(logging.INFO, dict(result.to_record()))
    return EXIT_OK


def _run_info(_: argparse.Namespace) -> int:
    info = project_info()
    _LOG.info("%s %s (%s)", info.distribution, info.version, info.package)
    return EXIT_OK


def _run_import(args: argparse.Namespace) -> int:
    return _report(lambda data_root: run_import(args.source, data_root))


def _run_corpus_build(args: argparse.Namespace) -> int:
    return _report(lambda data_root: run_corpus_build(args.manifest, data_root))


def _run_corpus_stage(args: argparse.Namespace) -> int:
    return _report(lambda data_root: stage_corpus(args.corpus, data_root))


def _run_corpus_verify(args: argparse.Namespace) -> int:
    return _report(lambda data_root: verify_corpus_frames(args.corpus, data_root))


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser independently for tests and future subcommands."""
    parser = argparse.ArgumentParser(prog="ss-track")
    subcommands = parser.add_subparsers(dest="command", required=True)

    info = subcommands.add_parser("info", help="show the installed project identity")
    info.set_defaults(handler=_run_info)

    source = subcommands.add_parser("import", help="import one declared recording")
    source.add_argument("--source", type=Path, required=True, help="recording declaration (YAML)")
    source.set_defaults(handler=_run_import)

    corpus = subcommands.add_parser("corpus", help="manage corpus versions")
    corpus_commands = corpus.add_subparsers(dest="corpus_command", required=True)
    build = corpus_commands.add_parser("build", help="build one corpus version")
    build.add_argument("--manifest", type=Path, required=True, help="corpus declaration (YAML)")
    build.set_defaults(handler=_run_corpus_build)
    stage = corpus_commands.add_parser("stage", help="stage decoded frames for a corpus version")
    stage.add_argument("--corpus", required=True, help="built corpus_id")
    stage.set_defaults(handler=_run_corpus_stage)
    verify = corpus_commands.add_parser(
        "verify", help="verify every staged frame and the source records it rests on"
    )
    verify.add_argument("--corpus", required=True, help="built corpus_id")
    verify.set_defaults(handler=_run_corpus_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected command and return a process status."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)
    status: int = args.handler(args)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
