"""`ss-track contracts`: the commands that read only the contract set, so they need no data root."""

import argparse
from pathlib import Path

from ss_track.commands import Subcommands
from ss_track.commands.report import reported
from ss_track.schema import list_contracts, validate_file
from ss_track.schema.compatibility.freeze import diff_contract, freeze_contract
from ss_track.schema.registry.contract import DISPOSITIONS
from ss_track.schema.views.docs import render_docs
from ss_track.schema.views.odcs import export_odcs


def add_contract_commands(subcommands: Subcommands) -> None:
    """Add `contracts` and every command under it."""
    contracts = subcommands.add_parser("contracts", help="read the published data contracts")
    commands = contracts.add_subparsers(dest="contracts_command", required=True)
    export = commands.add_parser("export", help="export contract catalog views")
    export.add_argument("--format", choices=("odcs",), required=True)
    export.add_argument("--out", type=Path, required=True)
    export.set_defaults(handler=lambda args: reported(lambda: export_odcs(args.out)))
    docs = commands.add_parser("docs", help="write contract reference Markdown")
    docs.add_argument("--out", type=Path, required=True)
    docs.set_defaults(handler=lambda args: reported(lambda: render_docs(args.out)))
    listing = commands.add_parser("list", help="list every contract and its frozen versions")
    listing.set_defaults(handler=_run_list)
    validate = commands.add_parser("validate", help="check one file under a frozen contract")
    validate.add_argument(
        "--file",
        type=Path,
        required=True,
        help="JSON record/result, or YAML with --contract declaration/<id>",
    )
    validate.add_argument(
        "--contract", help="<family>/<id>; taken from the file's kind when omitted"
    )
    validate.add_argument(
        "--version", help="an exact frozen version; the newest of the file's major when omitted"
    )
    validate.set_defaults(handler=_run_validate)
    _add_evolution_commands(commands)


def _add_evolution_commands(commands: Subcommands) -> None:
    for name, handler in (("diff", _run_diff), ("freeze", _run_freeze)):
        command = commands.add_parser(name, help=f"{name} a candidate contract")
        command.add_argument("contract", help="family/id")
        command.add_argument("--file", type=Path, required=True, help="candidate schema JSON")
        command.add_argument(
            "--root", type=Path, help="writable contract set; defaults to installed set"
        )
        command.set_defaults(handler=handler)
        if name == "freeze":
            command.add_argument("--summary", required=True)
            command.add_argument("--migration")
            command.add_argument("--disposition", choices=DISPOSITIONS)
            command.add_argument("--owner", help="owning capability for an initial contract")


def _run_list(_: argparse.Namespace) -> int:
    return reported(list_contracts)


def _run_validate(args: argparse.Namespace) -> int:
    return reported(
        lambda: validate_file(args.file, contract_name=args.contract, version=args.version)
    )


def _run_diff(args: argparse.Namespace) -> int:
    return reported(lambda: diff_contract(args.contract, args.file, args.root))


def _run_freeze(args: argparse.Namespace) -> int:
    return reported(
        lambda: freeze_contract(
            args.contract,
            args.file,
            root=args.root,
            summary=args.summary,
            migration=args.migration,
            disposition=args.disposition,
            owner=args.owner,
        )
    )
