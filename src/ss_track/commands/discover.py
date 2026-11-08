"""`ss-track discover`: discovery runs, links between recordings, and review of a run's windows."""

import argparse
from pathlib import Path

from ss_track.commands import Subcommands
from ss_track.commands.report import reported_on_data_root
from ss_track.corpus.discovery.run import run_discovery, verify_discovery_run
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.review.export import export_review
from ss_track.corpus.review.template import queue_review


def add_discover_commands(subcommands: Subcommands) -> None:
    """Add `discover` with `run`, `verify`, `links`, `queue` and `export` under it."""
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
    queue = commands.add_parser(
        "queue", help="report the windows a run offers for review and write a review file"
    )
    queue.add_argument("--run-id", required=True, help="discovery run_id")
    queue.add_argument("--out", type=Path, help="review file to write, every window undecided")
    queue.set_defaults(handler=_queue)
    export = commands.add_parser(
        "export", help="write the corpus declaration of the version a review makes of its run"
    )
    export.add_argument("--review", type=Path, required=True, help="reviewer decisions (YAML)")
    export.add_argument("--corpus-id", required=True, help="corpus_id of the frozen version")
    export.add_argument("--supersedes", help="corpus_id the frozen version supersedes")
    export.add_argument("--out", type=Path, required=True, help="corpus declaration to write")
    export.set_defaults(handler=_export)


def _run(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: run_discovery(args.plan, data_root))


def _verify(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: verify_discovery_run(args.run_id, data_root))


def _links(args: argparse.Namespace) -> int:
    request = LinkRequest(args.run_id, args.corpus, args.features, args.decisions)
    return reported_on_data_root(lambda data_root: write_links(request, data_root))


def _queue(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: queue_review(args.run_id, data_root, args.out))


def _export(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: export_review(
            args.review, args.corpus_id, args.out, data_root, supersedes=args.supersedes
        )
    )
