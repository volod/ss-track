"""One sealed record of exactly which frame bundles a corpus version staged.

A scenario pins this record's single hash rather than a list of bundles. It holds no path or clock,
so two stagings of one corpus version give one hash on any data root, and the corpus manifest hash
it carries binds that hash to the version's membership and splits.

It is written once, after the last bundle, and never rewritten. A later stage compares what it finds
with the record, so a changed bundle cannot carry the frame set along with it.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.corpus.frames import frames_root
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import SEAL_FIELD, read_sealed, require_schema, seal, write_sealed

FRAME_SET_KIND = "ss-track.frame-set"
FRAME_SET_SCHEMA_VERSION = 1
FRAME_SET_NAME = "frame-set.json"
MISSING = "missing"
REPLACED = "replaced"
UNNAMED = "unnamed"
_HIDDEN_PREFIX = "."

type BundleHashes = Mapping[str, str]
type Lines = dict[str, dict[str, Any]]


def frame_set_path(data_root: Path, corpus_id: str) -> Path:
    """Return the path of a corpus version's frame set, beside its manifest."""
    return frames_root(data_root, corpus_id).parent / FRAME_SET_NAME


def _line(
    bundle_id: str, stream: Mapping[str, Any], parent_id: str | None, hashes: BundleHashes
) -> dict[str, JsonValue]:
    """State one bundle and the source record under it. A case rests on its parent's record."""
    return {
        "stream_id": bundle_id,
        "parent_stream_id": parent_id,
        "bundle_sha256": hashes[bundle_id],
        "source_sha256": stream["source_sha256"],
        "source_manifest_sha256": stream["source_manifest_sha256"],
    }


def _seal_found(corpus: Mapping[str, Any], hashes: BundleHashes) -> dict[str, JsonValue]:
    """Seal what the corpus declares and staging found, in an order no declaration can change."""
    streams = {stream["stream_id"]: stream for stream in corpus["streams"]}
    lines = {name: _line(name, stream, None, hashes) for name, stream in streams.items()}
    for case in corpus["generated_cases"]:
        parent = case["parent_stream_id"]
        lines[case["case_id"]] = _line(case["case_id"], streams[parent], parent, hashes)
    return seal(
        {
            "kind": FRAME_SET_KIND,
            "schema_version": FRAME_SET_SCHEMA_VERSION,
            "corpus_id": corpus["corpus_id"],
            "corpus_manifest_sha256": corpus[SEAL_FIELD],
            "bundles": [lines[name] for name in sorted(lines)],
        }
    )


def _read(path: Path) -> dict[str, JsonValue]:
    record = read_sealed(path, FRAME_SET_KIND)
    require_schema(record, FRAME_SET_SCHEMA_VERSION, path)
    return record


def read_frame_set(data_root: Path, corpus_id: str) -> dict[str, JsonValue]:
    """Return a corpus version's sealed record, refusing a missing or damaged one."""
    return _read(frame_set_path(data_root, corpus_id))


def _lines(record: Mapping[str, Any]) -> Lines:
    """Index a record's bundles. A seal proves only that a record matches itself."""
    try:
        return {line["stream_id"]: line for line in record["bundles"]}
    except (KeyError, TypeError) as error:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED, "frame set is incomplete", {"record": FRAME_SET_NAME}
        ) from error


def _difference(
    bundle_id: str, pinned: dict[str, Any] | None, found: dict[str, Any] | None
) -> dict[str, JsonValue] | None:
    if pinned == found:
        return None
    if pinned is None:
        return {"stream_id": bundle_id, "reason": UNNAMED}
    if found is None:
        return {"stream_id": bundle_id, "reason": MISSING}
    return {
        "stream_id": bundle_id,
        "reason": REPLACED,
        "frame_set_bundle_sha256": pinned.get("bundle_sha256"),
        "bundle_sha256": found["bundle_sha256"],
    }


def _differences(pinned: Lines, found: Lines) -> list[JsonValue]:
    names = sorted(pinned.keys() | found.keys(), key=str)
    entries = (_difference(name, pinned.get(name), found.get(name)) for name in names)
    return [entry for entry in entries if entry is not None]


def _strays(found: Lines, root: Path) -> list[JsonValue]:
    """Name what sits among the bundles undeclared. Identifiers cannot start with a dot."""
    names = sorted(path.name for path in root.iterdir())
    return [
        {"stream_id": name, "reason": UNNAMED}
        for name in names
        if name not in found and not name.startswith(_HIDDEN_PREFIX)
    ]


def _require_match(
    pinned: Mapping[str, JsonValue], found: Mapping[str, JsonValue], root: Path
) -> None:
    """Refuse any difference, naming every bundle. A bundle no frame set names is not corpus."""
    found_lines = _lines(found)
    differences = _differences(_lines(pinned), found_lines) + _strays(found_lines, root)
    if differences or pinned[SEAL_FIELD] != found[SEAL_FIELD]:
        raise CorpusRefusal(
            RefusalCode.FRAME_SET_MISMATCH,
            f"staged bundles of {found['corpus_id']} differ from its frame set",
            {
                "corpus_id": found["corpus_id"],
                "frame_set_sha256": pinned[SEAL_FIELD],
                "found_frame_set_sha256": found[SEAL_FIELD],
                "frame_set_corpus_manifest_sha256": pinned.get("corpus_manifest_sha256"),
                "corpus_manifest_sha256": found["corpus_manifest_sha256"],
                "bundles": differences,
            },
        )


def commit_frame_set(
    corpus: Mapping[str, Any], hashes: BundleHashes, data_root: Path
) -> tuple[str, bool]:
    """Write the record after the last bundle, or compare with it, and say whether it was written.

    The caller holds the staging lock, so no bundle can change between finding and sealing.
    """
    corpus_id = str(corpus["corpus_id"])
    path = frame_set_path(data_root, corpus_id)
    found = _seal_found(corpus, hashes)
    first = not path.exists()
    _require_match(found if first else _read(path), found, frames_root(data_root, corpus_id))
    if first:
        write_sealed(path, found)
    return str(found[SEAL_FIELD]), first


def require_frame_set(corpus: Mapping[str, Any], hashes: BundleHashes, data_root: Path) -> str:
    """Return the record's hash once every staged bundle is shown to be the one it names."""
    corpus_id = str(corpus["corpus_id"])
    path = frame_set_path(data_root, corpus_id)
    if not path.is_file():
        raise CorpusRefusal(
            RefusalCode.FRAME_SET_NOT_STAGED,
            "no frame set: staging this corpus version has not finished",
            {"corpus_id": corpus_id},
        )
    found = _seal_found(corpus, hashes)
    _require_match(_read(path), found, frames_root(data_root, corpus_id))
    return str(found[SEAL_FIELD])
