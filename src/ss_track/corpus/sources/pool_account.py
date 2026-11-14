"""Count streams and cases by the collections recorded on their source."""

from pathlib import Path

from ss_track.core.refusal import JsonValue
from ss_track.corpus.sources.stored import load_source_record
from ss_track.corpus.versions.manifests import load_corpus_manifest


def account_corpus(corpus_id: str, data_root: Path) -> dict[str, JsonValue]:
    """Count each stream and case once per collection named by its source origin.

    A source with no origin is counted under provider and collection ``unknown``. A stream with two
    origins increments each collection and the unique count once.
    """
    manifest = load_corpus_manifest(corpus_id, data_root)
    streams = _rows(manifest.get("streams"))
    cases = _rows(manifest.get("generated_cases"))
    counts: dict[tuple[str, str], list[int]] = {}
    cache: dict[str, list[tuple[str, str]]] = {}
    for stream in streams:
        _add(counts, _origins(str(stream["source_sha256"]), data_root, cache), 0)
    for case in cases:
        _add(counts, _origins(str(case["source_sha256"]), data_root, cache), 1)
    return {
        "unique_stream_count": len(streams),
        "unique_case_count": len(cases),
        "collections": [
            {
                "provider": provider,
                "collection_id": collection_id,
                "stream_count": values[0],
                "case_count": values[1],
            }
            for (provider, collection_id), values in sorted(counts.items())
        ],
    }


def _rows(value: JsonValue) -> list[dict[str, JsonValue]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _origins(
    source: str, data_root: Path, cache: dict[str, list[tuple[str, str]]]
) -> list[tuple[str, str]]:
    found = cache.get(source)
    if found is None:
        found = _read_origins(load_source_record(source, data_root).get("origin"))
        cache[source] = found
    return found


def _read_origins(value: JsonValue) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return [("unknown", "unknown")]
    keys: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        provider = item.get("provider")
        collection = item.get("collection_id")
        if isinstance(provider, str) and isinstance(collection, str):
            keys.append((provider, collection))
    return keys or [("unknown", "unknown")]


def _add(counts: dict[tuple[str, str], list[int]], keys: list[tuple[str, str]], index: int) -> None:
    seen: set[tuple[str, str]] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        bucket = counts.setdefault(key, [0, 0])
        bucket[index] += 1
