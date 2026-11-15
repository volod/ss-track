"""`ss-track annotate`: validate labels, seeds and masks."""

import argparse
from pathlib import Path

from ss_track.annotate.result import AnnotationResult
from ss_track.annotate.validate import validate_labels, validate_mask, validate_seed
from ss_track.commands import Subcommands
from ss_track.commands.report import reported
from ss_track.corpus.declarations.fields import invalid


def add_annotate_commands(subcommands: Subcommands) -> None:
    """Add `annotate validate`."""
    annotate = subcommands.add_parser("annotate", help="validate labels, seeds and masks")
    commands = annotate.add_subparsers(dest="annotate_command", required=True)
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
