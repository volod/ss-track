"""`ss-track discover`: source acquisition, combined pools, discovery runs and link review."""

import argparse
from pathlib import Path

from ss_track.commands import Subcommands
from ss_track.commands.report import reported, reported_on_data_root
from ss_track.corpus.discovery.run import run_discovery, verify_discovery_run
from ss_track.corpus.evaluation.report import evaluate
from ss_track.corpus.links.interactive import review_interactively
from ss_track.corpus.links.portable import export_handoff, unpack_handoff
from ss_track.corpus.links.portable_accept import accept_handoff
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.review.audit_interactive import review_audit_interactively
from ss_track.corpus.review.blind import present_audit, unblind_audit
from ss_track.corpus.review.export import export_review
from ss_track.corpus.review.pass_interactive import review_pass_interactively
from ss_track.corpus.review.template import queue_review
from ss_track.corpus.sources.acquisition import AcquisitionRequest, acquire
from ss_track.corpus.sources.inventory import inventory_sources
from ss_track.corpus.sources.pool import prepare_pool


def add_discover_commands(subcommands: Subcommands) -> None:
    """Add `discover` and the commands that acquire, select, review and compare."""
    discover = subcommands.add_parser(
        "discover", help="propose candidate windows of staged frames for review"
    )
    commands = discover.add_subparsers(dest="discover_command", required=True)
    inventory = commands.add_parser("inventory", help="normalize an upstream source inventory")
    inventory.add_argument("--file", type=Path, required=True, help="source inventory declaration")
    inventory.add_argument("--out", type=Path, required=True, help="normalized inventory path")
    inventory.set_defaults(handler=_inventory)
    acquisition = commands.add_parser(
        "acquire", help="acquire an authorized pinned source selection"
    )
    acquisition.add_argument("--inventory", type=Path, required=True)
    acquisition.add_argument("--provider", choices=("zenodo", "huggingface"), required=True)
    acquisition.add_argument("--collection", required=True)
    acquisition.add_argument("--video", action="append", required=True)
    acquisition.add_argument("--metadata", action="append", default=[])
    acquisition.add_argument("--run-id", required=True)
    acquisition.add_argument("--download-budget", type=int, required=True)
    acquisition.add_argument("--extraction-budget", type=int, required=True)
    acquisition.add_argument("--authorized", action="store_true")
    acquisition.set_defaults(handler=_acquire)
    pool = commands.add_parser("pool", help="prepare a combined corpus from acquired collections")
    pool.add_argument("--declaration", type=Path, required=True, help="corpus pool declaration")
    pool.add_argument("--run-id", required=True, help="discovery-run id that stores the pool")
    pool.set_defaults(handler=_pool)
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
    evaluation = commands.add_parser("evaluate", help="compare two reviewed selection runs")
    evaluation.add_argument("--diverse-run", required=True)
    evaluation.add_argument("--uniform-run", required=True)
    for method in ("diverse", "uniform"):
        evidence = evaluation.add_mutually_exclusive_group(required=True)
        evidence.add_argument(f"--{method}-review", type=Path)
        evidence.add_argument(f"--{method}-freeze")
    evaluation.set_defaults(handler=_evaluate)
    links = commands.add_parser(
        "links", help="flag related recordings across groups and check reviewer decisions"
    )
    links.add_argument("--corpus", required=True, help="staged corpus_id")
    links.add_argument("--run-id", required=True, help="run id that keeps the link review")
    links.add_argument("--features", help="discovery run_id whose feature rows to compare")
    links.add_argument("--decisions", type=Path, help="reviewer link decisions (YAML)")
    links.set_defaults(handler=_links)
    review_links = commands.add_parser(
        "review-links", help="interactively review recording relationships and resume safely"
    )
    review_links.add_argument("--run-id", required=True, help="undecided link-review run id")
    review_links.add_argument("--reviewer", required=True, help="name of the human reviewer")
    review_links.set_defaults(handler=_review_links)
    review_pack = commands.add_parser(
        "review-pack", help="pack a media-free review handoff for an independently built corpus"
    )
    review_pack.add_argument("--run-id", required=True, help="link-review run id")
    review_pack.add_argument("--corpus", required=True, help="locally built corpus id")
    review_pack.add_argument("--identity-run", required=True, help="run for this host's hashes")
    review_pack.add_argument("--expires-on", required=True, help="last permitted UTC date")
    review_pack.add_argument("--out", type=Path, required=True, help="portable tar archive")
    review_pack.add_argument(
        "--recipe",
        type=Path,
        action="append",
        required=True,
        help="local creation input to include",
    )
    review_pack.add_argument("--reviewer", required=True, help="checkpoint reviewer identity")
    review_pack.set_defaults(handler=_review_pack)
    review_unpack = commands.add_parser(
        "review-unpack", help="extract creation inputs from a verified media-free handoff"
    )
    review_unpack.add_argument("--archive", type=Path, required=True)
    review_unpack.add_argument("--out", type=Path, required=True)
    review_unpack.add_argument("--authorized", action="store_true")
    review_unpack.set_defaults(handler=_review_unpack)
    review_accept = commands.add_parser(
        "review-accept", help="compare a local corpus and safely accept a review handoff"
    )
    review_accept.add_argument("--archive", type=Path, required=True)
    review_accept.add_argument("--identity-run", required=True, help="run for local staged hashes")
    review_accept.add_argument(
        "--comparison-run", required=True, help="run for comparison evidence"
    )
    review_accept.add_argument("--reviewer", required=True)
    review_accept.add_argument("--authorized", action="store_true")
    review_accept.set_defaults(handler=_review_accept)
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
    blind = commands.add_parser(
        "blind", help="present the common audit sample without selection or source cues"
    )
    blind.add_argument("--audit-id", required=True, help="id of this blinded audit")
    blind.add_argument("--run-id", action="append", required=True, dest="run_ids")
    blind.add_argument("--out", type=Path, required=True, help="directory to give the reviewer")
    blind.set_defaults(handler=_blind)
    _add_review_audit(commands)
    unblind = commands.add_parser(
        "unblind", help="map a blinded audit review back to per-run review files"
    )
    unblind.add_argument("--audit-id", required=True)
    unblind.add_argument("--review", type=Path, required=True, help="completed blinded review")
    unblind.add_argument("--out", type=Path, required=True, help="directory of per-run reviews")
    unblind.set_defaults(handler=_unblind)


def _add_review_audit(commands: Subcommands) -> None:
    review_audit = commands.add_parser(
        "review-audit", help="interactively review a blinded audit packet and resume safely"
    )
    review_audit.add_argument("--packet", type=Path, required=True, help="blinded audit packet")
    review_audit.add_argument("--reviewer", required=True, help="name of the human reviewer")
    review_audit.add_argument(
        "--review", type=Path, help="review file to write (default: <packet>/review-completed.yaml)"
    )
    declarations = ("declared", "not_declared")
    review_audit.add_argument("--independence", choices=declarations)
    review_audit.add_argument("--blinding", choices=declarations)
    review_audit.add_argument(
        "--no-autoplay", action="store_true", help="do not play each undecided item on arrival"
    )
    review_audit.set_defaults(handler=_review_audit)
    review_pass = commands.add_parser(
        "review-pass", help="interactively review every window a run selected and resume safely"
    )
    review_pass.add_argument("--run-id", required=True, help="discovery run_id")
    review_pass.add_argument(
        "--review", type=Path, required=True, help="the run's review, as discover unblind wrote it"
    )
    review_pass.add_argument("--reviewer", required=True, help="name of the pass reviewer")
    review_pass.add_argument(
        "--no-autoplay", action="store_true", help="do not play each unreviewed window on arrival"
    )
    review_pass.set_defaults(handler=_review_pass)


def _review_audit(args: argparse.Namespace) -> int:
    return reported(
        lambda: review_audit_interactively(
            args.packet,
            args.reviewer,
            args.review,
            args.independence,
            args.blinding,
            not args.no_autoplay,
        )
    )


def _review_pass(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: review_pass_interactively(
            args.run_id, args.review, args.reviewer, not args.no_autoplay, data_root
        )
    )


def _run(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: run_discovery(args.plan, data_root))


def _verify(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: verify_discovery_run(args.run_id, data_root))


def _links(args: argparse.Namespace) -> int:
    request = LinkRequest(args.run_id, args.corpus, args.features, args.decisions)
    return reported_on_data_root(lambda data_root: write_links(request, data_root))


def _review_links(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: review_interactively(args.run_id, args.reviewer, data_root)
    )


def _review_pack(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: export_handoff(
            data_root,
            args.run_id,
            args.corpus,
            args.identity_run,
            args.expires_on,
            args.out,
            args.recipe,
            args.reviewer,
        )
    )


def _review_unpack(args: argparse.Namespace) -> int:
    return reported(lambda: unpack_handoff(args.archive, args.out, args.authorized))


def _review_accept(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: accept_handoff(
            data_root,
            args.archive,
            args.identity_run,
            args.comparison_run,
            args.reviewer,
            args.authorized,
        )
    )


def _queue(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: queue_review(args.run_id, data_root, args.out))


def _blind(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: present_audit(args.audit_id, args.run_ids, args.out, data_root)
    )


def _unblind(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: unblind_audit(args.audit_id, args.review, args.out, data_root)
    )


def _export(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: export_review(
            args.review, args.corpus_id, args.out, data_root, supersedes=args.supersedes
        )
    )


def _evaluate(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: evaluate(
            data_root,
            args.diverse_run,
            args.uniform_run,
            args.diverse_review,
            args.uniform_review,
            args.diverse_freeze,
            args.uniform_freeze,
        )
    )


def _inventory(args: argparse.Namespace) -> int:
    return reported(lambda: inventory_sources(args.file, args.out))


def _pool(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: prepare_pool(args.declaration, args.run_id, data_root)
    )


def _acquire(args: argparse.Namespace) -> int:
    request = AcquisitionRequest(
        args.inventory,
        args.provider,
        args.collection,
        args.video,
        args.run_id,
        args.download_budget,
        args.extraction_budget,
        args.authorized,
        args.metadata,
    )
    return reported_on_data_root(lambda data_root: acquire(request, data_root))
