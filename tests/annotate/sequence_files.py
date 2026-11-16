"""A retained image sequence and the annotate commands that read it."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from ss_track.core.evidence.sealing import sha256_file
from ss_track.corpus.declarations.image_sequence import ImageMember, ImageSequence
from ss_track.corpus.sources.image_sequence import copy_sequence
from tests.annotate.support import DRAFT
from tests.corpus._images import image


def retain_sequence(
    folder: Path, widths: tuple[int, ...] = (8, 8), rate: Fraction | None = Fraction(25)
) -> tuple[Path, str]:
    """Copy an ordered PNG sequence and return its retained directory and identity."""
    raw = folder / "raw"
    raw.mkdir(parents=True)
    members = []
    for index, width in enumerate(widths):
        path = image(raw / f"{index}.png", index + 1, width, height=8)
        members.append(ImageMember(index, path, sha256_file(path)))
    stored = folder / "source.sequence"
    identity, _size = copy_sequence(ImageSequence(tuple(members), rate), stored)
    return stored, identity


def validate_command(kind: str, path: Path, source: Path, labels: Path | None = None) -> list[str]:
    """Return an `annotate validate` command for one source."""
    command = [
        "annotate",
        "validate",
        "--kind",
        kind,
        "--file",
        str(path),
        "--pack",
        str(DRAFT),
        "--source",
        str(source),
    ]
    if labels is not None:
        command.extend(["--labels", str(labels)])
    return command


def compare_command(folder: Path, source: Path) -> list[str]:
    """Return an `annotate compare` command for the pair written in `folder`."""
    return ["annotate", "compare", *_pair(folder, source)]


def freeze_command(folder: Path, source: Path) -> list[str]:
    """Return an `annotate freeze` command for the pair written in `folder`."""
    return [
        "annotate",
        "freeze",
        *_pair(folder, source),
        "--settlement",
        str(folder / "settlement.yaml"),
        "--labels-out",
        str(folder / "frozen.json"),
        "--revision-out",
        str(folder / "revision.json"),
    ]


def logged_record(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    """Return the last command record. The caller has set the log level."""
    return json.loads(caplog.records[-1].getMessage())


def _pair(folder: Path, source: Path) -> list[str]:
    return [
        "--left",
        str(folder / "left.yaml"),
        "--right",
        str(folder / "right.yaml"),
        "--pack",
        str(DRAFT),
        "--source",
        str(source),
        "--review",
        str(folder / "review.yaml"),
    ]
