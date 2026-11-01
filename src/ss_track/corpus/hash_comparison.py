"""Whether two hosts staged the same bytes, and which sources did not.

An equal frame-set hash proves every bundle equal, because the frame set names each bundle hash.
Unequal ones prove less: a source record can differ with every bundle equal, so the comparison
states which it was. It is kept on disk either way, because a negative result is worth the most.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.corpus.host_hashes import STAGED_HASHES_NAME, read_staged_hashes, run_directory
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import seal, write_sealed

HASH_COMPARISON_KIND = "ss-track.hash-comparison"
HASH_COMPARISON_SCHEMA_VERSION = 1
HASH_COMPARISON_NAME = "hash-comparison.json"
IDENTICAL = "identical"
DIFFERENT = "different"

type FrameLine = list[JsonValue]


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Two hosts that staged identical bytes. A difference is a refusal instead."""

    comparison: Mapping[str, JsonValue]
    record_path: Path

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return dict(self.comparison) | {"record_path": str(self.record_path)}


def _names(lines: Iterable[Mapping[str, Any]], key: str) -> set[str]:
    return {line[key] for line in lines}


def _unmatched(left: dict[str, Any], right: dict[str, Any]) -> list[JsonValue]:
    """Name what makes two records different questions, which no byte comparison can answer."""
    unmatched: list[JsonValue] = [
        field for field in ("corpus_id", "decode_policy_sha256") if left[field] != right[field]
    ]
    if _names(left["sources"], "source_sha256") != _names(right["sources"], "source_sha256"):
        unmatched.append("sources")
    if _names(left["bundles"], "stream_id") != _names(right["bundles"], "stream_id"):
        unmatched.append("bundles")
    return unmatched


def _require_comparable(left: dict[str, Any], right: dict[str, Any]) -> None:
    try:
        unmatched = _unmatched(left, right)
    except (KeyError, TypeError) as error:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "staged-hash record is incomplete",
            {"record": STAGED_HASHES_NAME, "field": str(error)},
        ) from error
    if unmatched:
        raise CorpusRefusal(
            RefusalCode.HASHES_NOT_COMPARABLE,
            "these records state different corpora, decoders or sources, so bytes cannot be "
            "compared across hosts",
            {"unmatched": unmatched},
        )


def _differing_frames(left: list[FrameLine], right: list[FrameLine]) -> list[int]:
    """Return every frame index whose PTS or hash differs, or that one side lacks."""
    left_lines = {line[0]: line for line in left}
    right_lines = {line[0]: line for line in right}
    indexes = left_lines.keys() | right_lines.keys()
    return sorted(
        int(str(index)) for index in indexes if left_lines.get(index) != right_lines.get(index)
    )


def _bundle_difference(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Describe one bundle. No differing frame means only its parent or identity moved."""
    differing = _differing_frames(left["frames"], right["frames"])
    return {
        "stream_id": left["stream_id"],
        "parent_stream_id": left["parent_stream_id"],
        "left_bundle_sha256": left["bundle_sha256"],
        "right_bundle_sha256": right["bundle_sha256"],
        "frame_count": len(left["frames"]),
        "differing_frames": len(differing),
        "first_differing_frame": differing[0] if differing else None,
    }


def _bundle_differences(left: dict[str, Any], right: dict[str, Any]) -> dict[str, list[JsonValue]]:
    """Group differing bundles by source. A case's differences belong to its parent's source."""
    right_lines = {line["stream_id"]: line for line in right["bundles"]}
    grouped: dict[str, list[JsonValue]] = {}
    for line in left["bundles"]:
        other = right_lines[line["stream_id"]]
        if line["bundle_sha256"] != other["bundle_sha256"]:
            entries = grouped.setdefault(line["source_sha256"], [])
            entries.append(_bundle_difference(line, other))
    return grouped


def _differing_sources(left: dict[str, Any], right: dict[str, Any]) -> list[JsonValue]:
    """Name each source that differs. A source record can differ with every bundle equal."""
    bundles = _bundle_differences(left, right)
    right_sources = {line["source_sha256"]: line for line in right["sources"]}
    differing: list[JsonValue] = []
    for source in left["sources"]:
        sha256 = source["source_sha256"]
        other = right_sources[sha256]
        record_differs = source["source_manifest_sha256"] != other["source_manifest_sha256"]
        if record_differs or sha256 in bundles:
            differing.append(
                {
                    "source_sha256": sha256,
                    "codec": source["codec"],
                    "source_pixel_format": source["source_pixel_format"],
                    "source_record_differs": record_differs,
                    "bundles": bundles.get(sha256, []),
                }
            )
    return differing


def _side(record: Mapping[str, Any]) -> dict[str, JsonValue]:
    return {
        "host": record["host"],
        "frame_set_sha256": record["frame_set_sha256"],
        "corpus_manifest_sha256": record["corpus_manifest_sha256"],
    }


def compare_staged_hashes(
    left_path: Path, right_path: Path, run_id: str, data_root: Path
) -> ComparisonResult:
    """Compare two hosts' records and keep the result, then refuse if they differ."""
    target = run_directory(data_root, run_id) / HASH_COMPARISON_NAME
    left, right = read_staged_hashes(left_path), read_staged_hashes(right_path)
    _require_comparable(left, right)
    equal = left["frame_set_sha256"] == right["frame_set_sha256"]
    comparison = seal(
        {
            "kind": HASH_COMPARISON_KIND,
            "schema_version": HASH_COMPARISON_SCHEMA_VERSION,
            "status": IDENTICAL if equal else DIFFERENT,
            "corpus_id": left["corpus_id"],
            "source_count": len(left["sources"]),
            "bundle_count": len(left["bundles"]),
            "left": _side(left),
            "right": _side(right),
            "sources": [] if equal else _differing_sources(left, right),
        }
    )
    write_sealed(target, comparison)
    if not equal:
        raise CorpusRefusal(
            RefusalCode.STAGED_HASHES_DIFFER,
            "these hosts staged different bytes, so identical bundles cannot be claimed",
            dict(comparison) | {"record_path": str(target)},
        )
    return ComparisonResult(comparison, target)
