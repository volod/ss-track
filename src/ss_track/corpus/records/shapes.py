"""Corpus-specific historic record shapes."""

from ss_track.core.evidence.read_window import Record, StatedShape
from ss_track.core.refusal import JsonValue
from ss_track.corpus.records.kinds import CORPUS_MANIFEST_KIND
from ss_track.schema.registry.contract import FACTS

TERMS_KEYS = ("retain_until", "derived_frames")


def _streams_without_terms(record: Record) -> list[str]:
    """Name each stream whose rights lack the source terms, reading no frame and no other field."""
    streams = record.get("streams")
    if not isinstance(streams, list):
        return []
    return [
        str(stream.get("stream_id"))
        for stream in streams
        if isinstance(stream, dict) and not _holds_terms(stream.get("rights"))
    ]


def _holds_terms(rights: JsonValue) -> bool:
    return isinstance(rights, dict) and all(key in rights for key in TERMS_KEYS)


def shapes(amend_command: str) -> tuple[StatedShape, ...]:
    return (
        StatedShape(
            kind=CORPUS_MANIFEST_KIND,
            major=3,
            name="corpus-3-without-source-terms",
            disposition=FACTS,
            remedy=f"record source terms with {amend_command} and build a new corpus version",
            lacking=_streams_without_terms,
        ),
    )
