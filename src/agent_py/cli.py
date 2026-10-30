"""Command-line entrypoint for starter project diagnostics."""

import argparse
import logging
from collections.abc import Sequence

from agent_py.metadata import project_info

_LOG = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser independently for tests and future subcommands."""
    parser = argparse.ArgumentParser(prog="agent-py")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("info", help="show the installed project identity")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected command and return a process status."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "info":
        info = project_info()
        _LOG.info("%s %s (%s)", info.distribution, info.version, info.package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
