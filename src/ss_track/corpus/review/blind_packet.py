"""The reviewer packet: a cue-free declaration and one picture per frame, under item ids.

Picture bytes follow from the staged frames alone. A picture file is named by its place in the
window, never by the source frame index or the stream. The same windows always write the same
bytes. Visual content can still show where the footage came from; the file names do not.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.cases.preview_png import encode_rgb_png
from ss_track.corpus.decoding.pixels import OUTPUT_PIXEL_FORMAT
from ss_track.corpus.review.blind_sample import AuditItem, AuditSample
from ss_track.corpus.review.queue import LOCKED_WITHOUT_POLICY
from ss_track.corpus.storage.layout import frames_root
from ss_track.corpus.storage.scratch import write_atomically

_MIN_DIGITS = 3
_GUIDE = (
    "Open items/<item-id>/ in frame order. A picture can show where the footage came from.",
    "This file names no recording, no filename, no model and no reason a window was offered.",
    "Name the reviewer and set reviewer_minutes.",
    "Set each decision to include or exclude.",
    "An observation is target_present, target_absent, confuser or unknown. It is not a label.",
    "An exclusion needs a reason: no_value, quality, sensitive, rights, duplicate,",
    "or other with a note. Leave a window you did not decide unreviewed.",
    "independence and blinding record what was declared. They do not show that it happened.",
)


def frame_sha256(pictures: Sequence[bytes]) -> str:
    """Return the hash of one item's pictures in display order."""
    return sha256_bytes(b"".join(pictures))


def _require_rgb(bundle: FrameBundle) -> None:
    if bundle.pixel_format == OUTPUT_PIXEL_FORMAT:
        return
    raise CorpusRefusal(
        RefusalCode.RECORD_TAMPERED,
        f"bundle record states pixel format {bundle.pixel_format}; blinded frames are rgb24",
        {"stream_id": bundle.stream_id, "pixel_format": bundle.pixel_format},
    )


def _picture_name(offset: int, count: int) -> str:
    digits = max(_MIN_DIGITS, len(str(count - 1)))
    return f"{offset:0{digits}d}.png"


def render_frames(
    corpus: Mapping[str, Any], data_root: Path, items: Sequence[AuditItem]
) -> dict[str, tuple[bytes, ...]]:
    """Return each item's PNG pictures, in frame order, keyed by item id."""
    corpus_id = str(corpus["corpus_id"])
    root = frames_root(data_root, corpus_id)
    bundles: dict[str, FrameBundle] = {}
    rendered: dict[str, tuple[bytes, ...]] = {}
    for item in items:
        bundle = bundles.get(item.stream_id)
        if bundle is None:
            bundle = open_corpus_bundle(item.stream_id, corpus, root)
            _require_rgb(bundle)
            bundles[item.stream_id] = bundle
        indexes = range(item.start_frame, item.end_frame)
        pictures = tuple(
            encode_rgb_png(bundle.width, bundle.height, bundle.read_frame(index))
            for index in indexes
        )
        rendered[item.item_id] = pictures
    return rendered


def _quoted(value: str) -> str:
    return json.dumps(value)


def presentation_text(audit_id: str, sample: AuditSample) -> str:
    """Return the blinded review template. It is not valid until a reviewer completes it."""
    lines = [f"# Blinded audit sample {_quoted(audit_id)}."]
    lines += [f"# {line}" for line in _GUIDE]
    withheld = sample.withheld_count()
    if withheld:
        lines.append(f"# Withheld: {withheld} window(s), {LOCKED_WITHOUT_POLICY}.")
    lines += [
        "schema_version: 1",
        f"audit_id: {_quoted(audit_id)}",
        'reviewer: ""',
        "independence: not_declared",
        "blinding: not_declared",
        "observations:" if sample.items else "observations: []",
    ]
    for item in sample.items:
        lines += [
            f"- item_id: {_quoted(item.item_id)}",
            "  decision: unreviewed",
        ]
    return "\n".join(lines) + "\n"


def packet_files(
    out: Path, audit_id: str, sample: AuditSample, pictures: Mapping[str, Sequence[bytes]]
) -> list[tuple[Path, bytes]]:
    """Return the packet's files and bytes, with paths that carry only item ids."""
    files = [(out / "review.yaml", presentation_text(audit_id, sample).encode("ascii"))]
    for item in sample.items:
        frames = pictures[item.item_id]
        for offset, payload in enumerate(frames):
            name = _picture_name(offset, len(frames))
            files.append((out / "items" / item.item_id / name, payload))
    return files


def place_files(files: Sequence[tuple[Path, bytes]]) -> bool:
    """Write files that are absent when every existing one matches. Return whether any was new.

    A path that already holds other bytes is refused before any new file is written.
    """
    for path, payload in files:
        if not path.exists():
            continue
        if path.is_file() and path.read_bytes() == payload:
            continue
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "the output path already holds something else; choose another path",
            {"path": str(path)},
        )
    wrote = False
    for path, payload in files:
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(path, payload)
        wrote = True
    return wrote


def packet_frames_match(review_path: Path, items: Sequence[Mapping[str, JsonValue]]) -> None:
    """Refuse pictures beside a review that are not the ones the private mapping hashed.

    A review submitted without its picture directory is still read. A directory that is present
    and differs is a different packet.
    """
    root = review_path.parent / "items"
    if not root.exists():
        return
    for item in items:
        item_id = str(item["item_id"])
        directory = root / item_id
        if not directory.is_dir():
            raise CorpusRefusal(
                RefusalCode.RECORD_INVALID,
                "blinded frames do not match the private mapping",
                {"item_id": item_id},
            )
        frames = sorted(path for path in directory.iterdir() if path.suffix == ".png")
        found = frame_sha256(tuple(path.read_bytes() for path in frames))
        if found != item["frame_sha256"]:
            raise CorpusRefusal(
                RefusalCode.RECORD_INVALID,
                "blinded frames do not match the private mapping",
                {"item_id": item_id},
            )
