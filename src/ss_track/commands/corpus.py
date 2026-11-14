"""`ss-track import` and `ss-track corpus`: the commands that act on the data root."""

import argparse
from pathlib import Path

from ss_track.commands import Subcommands
from ss_track.commands.report import reported_on_data_root
from ss_track.corpus import (
    amend_source_terms,
    compare_staged_hashes,
    record_staged_hashes,
    redecode_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus import build_corpus as run_corpus_build
from ss_track.corpus import import_source as run_import
from ss_track.corpus.cases.preview import preview_stream
from ss_track.corpus.descriptors.descriptor import RESTRICTED, VISIBILITIES, describe_corpus
from ss_track.corpus.review.freeze import freeze_corpus


def add_corpus_commands(subcommands: Subcommands) -> None:
    """Add `import`, and `corpus` with every command under it."""
    source = subcommands.add_parser("import", help="import one declared recording")
    source.add_argument("--source", type=Path, required=True, help="recording declaration (YAML)")
    source.add_argument(
        "--amend-terms",
        action="store_true",
        help=("record new rights and sensitivity, listing versions that pin the replaced record"),
    )
    source.add_argument(
        "--redecode",
        action="store_true",
        help=(
            "decode stored bytes again under the installed policy, "
            "listing versions that pin the old record"
        ),
    )
    source.set_defaults(handler=_run_import)

    corpus = subcommands.add_parser("corpus", help="manage corpus versions")
    corpus_commands = corpus.add_subparsers(dest="corpus_command", required=True)
    build = corpus_commands.add_parser("build", help="build one corpus version")
    build.add_argument("--manifest", type=Path, required=True, help="corpus declaration (YAML)")
    build.set_defaults(handler=_run_corpus_build)
    describe = corpus_commands.add_parser("describe", help="write or replace a corpus descriptor")
    describe.add_argument("--corpus", required=True)
    describe.add_argument("--declaration", type=Path, required=True)
    describe.add_argument("--visibility", choices=VISIBILITIES, default=RESTRICTED)
    describe.set_defaults(handler=_run_corpus_describe)
    stage = corpus_commands.add_parser("stage", help="stage decoded frames for a corpus version")
    stage.add_argument("--corpus", required=True, help="built corpus_id")
    stage.set_defaults(handler=_run_corpus_stage)
    verify = corpus_commands.add_parser(
        "verify", help="verify every staged frame and the source records it rests on"
    )
    verify.add_argument("--corpus", required=True, help="built corpus_id")
    verify.set_defaults(handler=_run_corpus_verify)
    hashes = corpus_commands.add_parser(
        "hashes", help="record a verified corpus's hashes and this host, for comparison"
    )
    hashes.add_argument("--corpus", required=True, help="staged corpus_id")
    hashes.add_argument("--run-id", required=True, help="run that keeps the record")
    hashes.set_defaults(handler=_run_corpus_hashes)
    compare = corpus_commands.add_parser(
        "compare", help="compare the staged hashes that two hosts recorded"
    )
    compare.add_argument("--left", type=Path, required=True, help="one staged-hashes.json")
    compare.add_argument("--right", type=Path, required=True, help="the other staged-hashes.json")
    compare.add_argument("--run-id", required=True, help="run that keeps the comparison")
    compare.set_defaults(handler=_run_corpus_compare)
    preview = corpus_commands.add_parser(
        "preview", help="write a contact sheet of one parent frame and its generated cases"
    )
    preview.add_argument("--corpus", required=True, help="built corpus_id")
    preview.add_argument("--stream", required=True, help="parent stream_id")
    preview.add_argument("--frame", type=int, required=True, help="zero-based source frame index")
    preview.add_argument("--out", type=Path, required=True, help="PNG file to write")
    preview.set_defaults(handler=_run_corpus_preview)
    freeze = corpus_commands.add_parser(
        "freeze", help="seal a staged version as the one a review makes of its discovery run"
    )
    freeze.add_argument("--corpus", required=True, help="staged corpus_id to freeze")
    freeze.add_argument("--review", type=Path, required=True, help="reviewer decisions (YAML)")
    freeze.add_argument("--links", required=True, help="run id of this version's link review")
    freeze.set_defaults(handler=_run_corpus_freeze)


def _run_import(args: argparse.Namespace) -> int:
    if args.redecode:
        return reported_on_data_root(
            lambda data_root: redecode_source(args.source, data_root, amend_terms=args.amend_terms)
        )
    action = amend_source_terms if args.amend_terms else run_import
    return reported_on_data_root(lambda data_root: action(args.source, data_root))


def _run_corpus_build(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: run_corpus_build(args.manifest, data_root))


def _run_corpus_describe(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: describe_corpus(args.corpus, args.declaration, data_root, args.visibility)
    )


def _run_corpus_stage(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: stage_corpus(args.corpus, data_root))


def _run_corpus_verify(args: argparse.Namespace) -> int:
    return reported_on_data_root(lambda data_root: verify_corpus_frames(args.corpus, data_root))


def _run_corpus_hashes(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: record_staged_hashes(args.corpus, args.run_id, data_root)
    )


def _run_corpus_compare(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: compare_staged_hashes(args.left, args.right, args.run_id, data_root)
    )


def _run_corpus_preview(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: preview_stream(args.corpus, args.stream, args.frame, args.out, data_root)
    )


def _run_corpus_freeze(args: argparse.Namespace) -> int:
    return reported_on_data_root(
        lambda data_root: freeze_corpus(args.corpus, args.review, args.links, data_root)
    )
