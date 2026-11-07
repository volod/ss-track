"""Command-line entrypoint: the root parser, `ss-track info`, and `main`.

Each command group lives in `ss_track.commands`, and `commands.report` states how every command
reports its one JSON record and exit status.
"""

import argparse
import logging
from collections.abc import Sequence

from ss_track.commands.contracts import add_contract_commands
from ss_track.commands.corpus import add_corpus_commands
from ss_track.commands.discover import add_discover_commands
from ss_track.commands.report import EXIT_OK
from ss_track.core.metadata import project_info

_LOG = logging.getLogger(__name__)


def _run_info(_: argparse.Namespace) -> int:
    info = project_info()
    _LOG.info("%s %s (%s)", info.distribution, info.version, info.package)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser independently for tests and future subcommands."""
    parser = argparse.ArgumentParser(prog="ss-track")
    subcommands = parser.add_subparsers(dest="command", required=True)

    info = subcommands.add_parser("info", help="show the installed project identity")
    info.set_defaults(handler=_run_info)

    add_corpus_commands(subcommands)
    add_discover_commands(subcommands)
    add_contract_commands(subcommands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected command and return a process status."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)
    status: int = args.handler(args)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
