"""`ss-track discover`: write and verify a discovery run, and review links between recordings."""

import argparse
from pathlib import Path

from ss_track.commands import Subcommands
from ss_track.commands.report import reported_on_data_root
from ss_track.corpus.discovery.run import run_discovery, verify_discovery_run
from ss_track.corpus.links.run import LinkRequest, write_links


def add_discover_commands(subcommands: Subcommands) -> None:
    """Add `discover` with `run`, `verify` and `links` under it."""
    discover = subcommands.add_parser(
        "discover", help="propose candidate windows of staged frames for review"
    )
    commands = discover.add_subparsers(dest="discover_command", required=True)
    run = commands.add_parser(
        "run", help="embed staged frames, map ss-video hints and write one discovery run"
    )
    run.add_argument("--plan", type=Path, required=True, help="discovery plan (YAML)")
    run.set_defaults(handler=_run)
    verify = commands.add_parser(
        "verify", help="verify a discovery run against the corpus version it read"
    )
    verify.add_argument("--run-id", required=True, help="discovery run_id")
    verify.set_defaults(handler=_verify)
    links = commands.add_parser(
        "links", help="flag related recordings across groups and check reviewer decisions"
    )
    links.add_argument("--corpus", required=True, help="staged corpus_id")
    links.add_argument("--run-id", required=True, help="run id that keeps the link review")
    links.add_argument("--features", help="discovery run_id whose feature rows to compare")
    links.add_argument("--decisions", type=Path, help="reviewer link decisions (YAML)")
    links.set_defaults(handler=_links)


def _run(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: run_discovery(args.plan, data_root))


def _verify(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: verify_discovery_run(args.run_id, data_root))


def _links(args: argparse.Namespace) -> int:
    request = LinkRequest(args.run_id, args.corpus, args.features, args.decisions)
    return reported_on_data_root(lambda data_root: write_links(request, data_root))
