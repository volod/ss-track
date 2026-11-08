"""Join acquired YAML, CSV and source-link files to videos by explicit evidence only.

A file joins a video when it names that video's path, a sibling metadata stem matches one video, or
a source-link line names the path or exactly that video's recorded source reference. Collection
vocabulary and a line that names no video stay unresolved. Nothing here sets rights or a label.
"""

from pathlib import Path, PurePosixPath

import yaml

from ss_track.core.strict_yaml import parse_unique_document
from ss_track.corpus.sources.metadata_claims import (
    MAX_METADATA_BYTES,
    Claims,
    Evidence,
    Unresolved,
    bucket,
    usable,
)
from ss_track.corpus.sources.metadata_text import csv_file, link_file

_YAML = {".yaml", ".yml"}


def join_metadata(
    videos: dict[str, str | None], files: tuple[tuple[str, Path, str], ...]
) -> tuple[dict[str, Evidence], tuple[Unresolved, ...]]:
    """Join metadata to `videos`, mapping each path to its inventory source reference."""
    found: dict[str, Claims] = {}
    pending: list[Unresolved] = []
    for path, local, digest in sorted(files, key=_rank):
        _one_file(path, local, digest, videos, found, pending)
    evidence = {path: claims.evidence() for path, claims in found.items()}
    for path, claims in found.items():
        pending.extend(
            Unresolved("conflicting_claim", path, detail) for _field, detail in claims.conflicts
        )
    return evidence, tuple(pending)


def _rank(item: tuple[str, Path, str]) -> tuple[int, str]:
    suffix = PurePosixPath(item[0]).suffix.lower()
    order = {".yaml": 0, ".yml": 0, ".csv": 1, ".txt": 2}
    return order.get(suffix, 3), item[0]


def _text(path: Path) -> str | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if len(payload) > MAX_METADATA_BYTES:
        return None
    try:
        return payload.decode("ascii")
    except UnicodeError:
        return None


def _one_file(
    path: str,
    local: Path,
    digest: str,
    videos: dict[str, str | None],
    found: dict[str, Claims],
    pending: list[Unresolved],
) -> None:
    text = _text(local)
    if text is None:
        pending.append(Unresolved("unmatched_metadata", path, f"{path} could not be read"))
        return
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in _YAML:
        _yaml_file(path, text, digest, videos, found, pending)
    elif suffix == ".csv":
        csv_file(path, text, digest, set(videos), found, pending)
    elif suffix == ".txt":
        link_file(path, text, digest, videos, found, pending)
    else:
        pending.append(Unresolved("unmatched_metadata", path, f"{path} has no join rule"))


def _yaml_file(
    path: str,
    text: str,
    digest: str,
    videos: dict[str, str | None],
    found: dict[str, Claims],
    pending: list[Unresolved],
) -> None:
    try:
        document = parse_unique_document(text)
    except (yaml.YAMLError, RecursionError):
        pending.append(Unresolved("unmatched_metadata", path, f"{path} could not be read"))
        return
    if not isinstance(document, dict):
        pending.append(Unresolved("unmatched_metadata", path, f"{path} matched no video"))
        return
    target = _yaml_target(path, document, set(videos))
    if target is None:
        pending.append(Unresolved("unmatched_metadata", path, f"{path} matched no video"))
        return
    _yaml_fields(path, document, digest, target, bucket(found, target))


def _yaml_target(path: str, document: dict[object, object], videos: set[str]) -> str | None:
    named = document.get("path", document.get("video"))
    if named is not None:
        usable_path = usable(named)
        return usable_path if usable_path in videos else None
    return _stem(path, videos)


def _stem(path: str, videos: set[str]) -> str | None:
    suffix = PurePosixPath(path).suffix
    stem = path[: -len(suffix)] if suffix else ""
    matches = [video for video in videos if PurePosixPath(video).with_suffix("").as_posix() == stem]
    if len(matches) == 1:
        return matches[0]
    return None


def _yaml_fields(
    path: str, document: dict[object, object], digest: str, video: str, claims: Claims
) -> None:
    source = _first(document, ("source", "url", "source_url"))
    annotation = _first(document, ("annotation", "annotation_path"))
    if source is not None:
        claims.add("source_reference", source, path, digest, video)
    if annotation is not None:
        claims.add("annotation_reference", annotation, path, digest, video)
    license_name = usable(document.get("license"))
    if license_name is not None:
        claims.add("license", license_name, path, digest, video)


def _first(document: dict[object, object], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = usable(document.get(name))
        if value is not None:
            return value
    return None
