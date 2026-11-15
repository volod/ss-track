"""`ss-track annotate`: validate, compare, freeze and derive labels."""

import argparse
from pathlib import Path

from ss_track.annotate.derive import derive_corpus
from ss_track.annotate.derive_result import DeriveResult
from ss_track.annotate.result import AnnotationResult
from ss_track.annotate.review import compare_labels, freeze_labels
from ss_track.annotate.review_result import ReviewResult
from ss_track.annotate.validate import validate_labels, validate_mask, validate_seed
from ss_track.commands import Subcommands
from ss_track.commands.report import reported, reported_on_data_root
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
            "Coordinates must use the stored orientation of the video file. "
            "An unverifiable label is reported unscorable and is not a score."
        ),
    )
    validate.add_argument("--kind", required=True, choices=("label", "seed", "mask"))
    validate.add_argument("--file", type=Path, required=True)
    validate.add_argument("--pack", type=Path, required=True, help="scenario pack declaration")
    validate.add_argument("--source", type=Path, required=True, help="video file modules receive")
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
    compare.add_argument("--review", type=Path, required=True, help="review plan")
    compare.set_defaults(handler=_run_compare)


def _add_freeze(commands: Subcommands) -> None:
    freeze = commands.add_parser(
        "freeze",
        help="freeze one hashed label revision",
        description=(
            "Settle disagreements and write one label revision plus a sealed record. "
            "A required disagreement with no decision is refused. "
            "A disagreement outside the review stays unknown. The record keeps both "
            "annotator document hashes as the sensitivity band and has no score."
        ),
    )
    _add_pair(freeze)
    freeze.add_argument("--review", type=Path, required=True, help="review plan")
    freeze.add_argument("--settlement", type=Path, required=True, help="recorded decisions")
    freeze.add_argument("--labels-out", type=Path, required=True, help="frozen label document")
    freeze.add_argument("--revision-out", type=Path, required=True, help="sealed revision record")
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
    command.add_argument("--source", type=Path, required=True, help="video file modules receive")


def _run_validate(arguments: argparse.Namespace) -> int:
    return reported(lambda: _validate(arguments))


def _validate(arguments: argparse.Namespace) -> AnnotationResult:
    kind = str(arguments.kind)
    path = arguments.file
    pack = arguments.pack
    source = arguments.source
    if kind == "label":
        return validate_labels(path, pack, source)
    if arguments.labels is None:
        raise invalid("--labels is required for a seed or a mask")
    if kind == "seed":
        return validate_seed(path, arguments.labels, pack, source)
    return validate_mask(path, arguments.labels, pack, source)


def _run_compare(arguments: argparse.Namespace) -> int:
    return reported(lambda: _compare(arguments))


def _run_freeze(arguments: argparse.Namespace) -> int:
    return reported(lambda: _freeze(arguments))


def _run_derive(arguments: argparse.Namespace) -> int:
    return reported_on_data_root(lambda root: _derive(arguments, root))


def _compare(arguments: argparse.Namespace) -> ReviewResult:
    return compare_labels(
        arguments.left, arguments.right, arguments.pack, arguments.source, arguments.review
    )


def _freeze(arguments: argparse.Namespace) -> ReviewResult:
    return freeze_labels(
        arguments.left,
        arguments.right,
        arguments.pack,
        arguments.source,
        arguments.review,
        arguments.settlement,
        arguments.labels_out,
        arguments.revision_out,
    )


def _derive(arguments: argparse.Namespace, root: Path) -> DeriveResult:
    return derive_corpus(str(arguments.corpus), arguments.pack, root)
