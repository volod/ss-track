"""Join CSV rows and source-link lines when they name a video exactly."""

import csv
import io
from pathlib import PurePosixPath

from ss_track.corpus.sources.metadata_claims import Claims, Unresolved, bucket, usable


def csv_file(
    path: str,
    text: str,
    digest: str,
    videos: set[str],
    found: dict[str, Claims],
    pending: list[Unresolved],
) -> None:
    """Apply CSV rows whose `name` is one video path or that path without its suffix."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or rows[0].count("name") != 1:
        pending.append(Unresolved("unmatched_metadata", path, f"{path} matched no video"))
        return
    header = rows[0]
    name_at = header.index("name")
    license_at = header.index("license") if header.count("license") == 1 else None
    for index, row in enumerate(rows[1:], start=1):
        _csv_row(path, digest, videos, found, pending, name_at, license_at, index, row)


def link_file(
    path: str,
    text: str,
    digest: str,
    videos: dict[str, str | None],
    found: dict[str, Claims],
    pending: list[Unresolved],
) -> None:
    """Apply source lines that name a video path or its recorded source reference."""
    for index, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            _link_line(path, line.strip(), index, digest, videos, found, pending)


def _csv_row(
    path: str,
    digest: str,
    videos: set[str],
    found: dict[str, Claims],
    pending: list[Unresolved],
    name_at: int,
    license_at: int | None,
    index: int,
    row: list[str],
) -> None:
    name = usable(row[name_at]) if name_at < len(row) else None
    target = None if name is None else _named(name, videos)
    if target is None:
        pending.append(
            Unresolved("unmatched_metadata", path, f"{path} row {index} matched no video")
        )
        return
    claims = bucket(found, target)
    if license_at is None or license_at >= len(row):
        return
    license_name = usable(row[license_at])
    if license_name is not None:
        claims.add("license", license_name, path, digest, target)


def _named(name: str, videos: set[str]) -> str | None:
    if name in videos:
        return name
    matches = [video for video in videos if PurePosixPath(video).with_suffix("").as_posix() == name]
    if len(matches) == 1:
        return matches[0]
    return None


def _link_line(
    path: str,
    line: str,
    index: int,
    digest: str,
    videos: dict[str, str | None],
    found: dict[str, Claims],
    pending: list[Unresolved],
) -> None:
    left, separator, right = line.partition(" - ")
    left, right = left.strip(), right.strip()
    named = [video for video in videos if _mentions(line, video)]
    by_source = [video for video, source in videos.items() if source is not None and source == left]
    targets = list(dict.fromkeys([*named, *by_source]))
    source = usable(left)
    license_name = usable(right) if separator else None
    if not targets:
        pending.append(
            Unresolved("unmatched_source_link", path, _detail(path, index, line, source))
        )
        return
    for video in targets:
        _apply_link(path, digest, source, license_name, video, bucket(found, video))


def _apply_link(
    path: str, digest: str, source: str | None, license_name: str | None, video: str, claims: Claims
) -> None:
    if source is not None and "://" in source:
        claims.add("source_reference", source, path, digest, video)
    if license_name is not None:
        claims.add("license", license_name, path, digest, video)


def _detail(path: str, index: int, line: str, source: str | None) -> str:
    detail = f"{path} line {index} matched no video"
    if source is not None and "://" in source:
        return f"{detail}: {source}"
    plain = usable(line)
    if plain is not None and "://" not in line:
        return f"{detail}: {plain}"
    return detail


def _mentions(line: str, video: str) -> bool:
    start = 0
    while True:
        found = line.find(video, start)
        if found < 0:
            return False
        before = line[found - 1] if found else " "
        end = found + len(video)
        after = line[end] if end < len(line) else " "
        if before in " \t" and after in " \t":
            return True
        start = found + 1
