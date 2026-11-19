"""`ss-track annotate`: validate, compare, freeze and derive labels."""

import argparse
from pathlib import Path

from ss_track.annotate.derivation.derive import derive_corpus
from ss_track.annotate.derivation.result import DeriveResult
from ss_track.annotate.review.freeze import ReviewInputs, compare_labels, freeze_labels
from ss_track.annotate.review.result import ReviewResult
from ss_track.annotate.sources.corpus_stream import stream_target
from ss_track.annotate.validation.result import AnnotationResult
from ss_track.annotate.validation.validate import validate_labels, validate_mask, validate_seed
from ss_track.commands import Subcommands
from ss_track.commands.report import (
    check_root_holding,
    checked_data_root,
    reported,
    reported_on_data_root,
)
from ss_track.corpus.declarations.fields import invalid


def add_annotate_commands(subcommands: Subcommands) -> None:
    """Add `annotate validate`, `compare`, `freeze` and `derive`."""
    annotate = subcommands.add_parser(
        "annotate", help="validate, compare, freeze and derive labels"
    )
    commands = annotate.add_subparsers(dest="annotate_command", required=True)
    _add_validate(commands)
    _add_compare(commands)
    _add_freeze(commands)
    _add_derive(commands)


def _add_validate(commands: Subcommands) -> None:
    validate = commands.add_parser(
        "validate",
        help="check one label, seed or mask document",
        description=(
            "Validate visibility, geometry, identity, motion events, a seed or a mask. "
            "Coordinates must use the stored orientation of the source. "
            "The source is a video file or a retained image sequence. "
            "A file that holds more than one video stream names one by its index. "
            "An unverifiable label is reported unscorable and is not a score."
        ),
    )
    validate.add_argument("--kind", required=True, choices=("label", "seed", "mask"))
    validate.add_argument("--file", type=Path, required=True)
    validate.add_argument("--pack", type=Path, required=True, help="scenario pack declaration")
    _add_source(validate)
    validate.add_argument("--labels", type=Path, help="label document, required for a seed or mask")
    validate.set_defaults(handler=_run_validate)


def _add_compare(commands: Subcommands) -> None:
    compare = commands.add_parser(
        "compare",
        help="report disagreements between two label documents",
        description=(
            "Report every field that differs between two label documents of one source. "
            "The annotator id is not a disagreement. A difference is canonical JSON. "
            "The command succeeds when the documents can be compared, including when they differ."
        ),
    )
    _add_pair(compare)
    _add_source(compare)
    compare.add_argument("--review", type=Path, required=True, help="review plan")
    compare.set_defaults(handler=_run_compare)


def _add_freeze(commands: Subcommands) -> None:
    freeze = commands.add_parser(
        "freeze",
        help="freeze one hashed label revision",
        description=(
            "Settle disagreements and write one label revision plus a sealed record. "
            "Name the source and both output files, or name a corpus stream with --corpus "
            "and --stream to read its stored source and write under that stream. "
            "A required disagreement with no decision is refused. "
            "A disagreement outside the review stays unknown. The record keeps both "
            "annotator document hashes as the sensitivity band and has no score."
        ),
    )
    _add_pair(freeze)
    _add_source(freeze, required=False)
    freeze.add_argument("--review", type=Path, required=True, help="review plan")
    freeze.add_argument("--settlement", type=Path, required=True, help="recorded decisions")
    freeze.add_argument("--labels-out", type=Path, help="frozen label document")
    freeze.add_argument("--revision-out", type=Path, help="sealed revision record")
    freeze.add_argument("--corpus", help="corpus version whose stream these labels belong to")
    freeze.add_argument("--stream", help="stream id; replaces --source and both output paths")
    freeze.set_defaults(handler=_run_freeze)


def _add_derive(commands: Subcommands) -> None:
    derive = commands.add_parser(
        "derive",
        help="derive a label revision for each generated case",
        description=(
            "Read each parent's frozen revision and apply the stored label transform. "
            "A parent with no frozen labels leaves its cases unscorable. "
            "Derived labels are written under the corpus and are not edited by hand."
        ),
    )
    derive.add_argument("--corpus", required=True, help="corpus version id")
    derive.add_argument("--pack", type=Path, required=True, help="scenario pack declaration")
    derive.set_defaults(handler=_run_derive)


def _add_pair(command: argparse.ArgumentParser) -> None:
    command.add_argument("--left", type=Path, required=True, help="first reviewer's labels")
    command.add_argument("--right", type=Path, required=True, help="second reviewer's labels")
    command.add_argument("--pack", type=Path, required=True, help="scenario pack declaration")


def _add_source(command: argparse.ArgumentParser, *, required: bool = True) -> None:
    command.add_argument(
        "--source", type=Path, required=required, help="video file or retained image sequence"
    )
    command.add_argument(
        "--video-stream-index",
        type=int,
        help="zero-based video stream of a file that holds more than one",
    )


def _run_validate(arguments: argparse.Namespace) -> int:
    return reported(lambda: _validate(arguments))


def _validate(arguments: argparse.Namespace) -> AnnotationResult:
    kind = str(arguments.kind)
    path = arguments.file
    pack = arguments.pack
    source = arguments.source
    stream = arguments.video_stream_index
    if kind == "label":
        return validate_labels(path, pack, source, stream)
    if arguments.labels is None:
        raise invalid("--labels is required for a seed or a mask")
    if kind == "seed":
        return validate_seed(path, arguments.labels, pack, source, stream)
    return validate_mask(path, arguments.labels, pack, source, stream)


def _run_compare(arguments: argparse.Namespace) -> int:
    return reported(lambda: _compare(arguments))


def _run_freeze(arguments: argparse.Namespace) -> int:
    return reported(lambda: _freeze(arguments))


def _run_derive(arguments: argparse.Namespace) -> int:
    return reported_on_data_root(lambda root: _derive(arguments, root))


def _compare(arguments: argparse.Namespace) -> ReviewResult:
    return compare_labels(_review_inputs(arguments))


def _freeze(arguments: argparse.Namespace) -> ReviewResult:
    paths = (arguments.source, arguments.labels_out, arguments.revision_out)
    if arguments.corpus is None and arguments.stream is None:
        if None in paths:
            raise invalid(
                "name --source, --labels-out and --revision-out, or --corpus and --stream"
            )
        check_root_holding(arguments.labels_out, arguments.revision_out)
        return freeze_labels(
            _review_inputs(arguments),
            arguments.settlement,
            arguments.labels_out,
            arguments.revision_out,
        )
    if arguments.corpus is None or arguments.stream is None:
        raise invalid("--corpus and --stream are given together")
    if any(item is not None for item in (*paths, arguments.video_stream_index)):
        raise invalid(
            "--corpus and --stream replace --source, --video-stream-index and both output paths"
        )
    target = stream_target(str(arguments.corpus), str(arguments.stream), checked_data_root())
    inputs = ReviewInputs(
        arguments.left,
        arguments.right,
        arguments.pack,
        target.source,
        arguments.review,
        target.video_stream_index,
    )
    return freeze_labels(
        inputs, arguments.settlement, target.labels_out, target.revision_out, stream=target.stream
    )


def _review_inputs(arguments: argparse.Namespace) -> ReviewInputs:
    return ReviewInputs(
        arguments.left,
        arguments.right,
        arguments.pack,
        arguments.source,
        arguments.review,
        arguments.video_stream_index,
    )


def _derive(arguments: argparse.Namespace, root: Path) -> DeriveResult:
    return derive_corpus(str(arguments.corpus), arguments.pack, root)
