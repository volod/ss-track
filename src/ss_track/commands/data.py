"""`ss-track data`: housekeeping of the data root."""

import argparse

from ss_track.commands import Subcommands
from ss_track.commands.report import reported_on_data_root
from ss_track.core.clean import clean_data_root
from ss_track.core.clean_kinds import KINDS


def add_data_commands(subcommands: Subcommands) -> None:
    """Add `data clean`."""
    data = subcommands.add_parser("data", help="housekeeping of the data root")
    data_commands = data.add_subparsers(dest="data_command", required=True)
    clean = data_commands.add_parser(
        "clean",
        help="plan or remove registered kinds of reproducible artifact",
        description=(
            "Plan, and with --apply remove, the named kinds of reproducible artifact. Sealed "
            "records, imported sources, declarations and review decisions are never removed."
        ),
    )
    clean.add_argument(
        "--kind", action="append", required=True, choices=sorted(KINDS), help="kind to clean"
    )
    clean.add_argument("--corpus", action="append", default=[], help="corpus version to clean")
    clean.add_argument("--run-id", action="append", default=[], help="run to clean")
    clean.add_argument("--apply", action="store_true", help="remove the planned entries")
    clean.set_defaults(handler=_run_clean)


def _run_clean(arguments: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: clean_data_root(
            data_root,
            list(arguments.kind),
            corpora=list(arguments.corpus),
            runs=list(arguments.run_id),
            apply=bool(arguments.apply),
        )
    )
