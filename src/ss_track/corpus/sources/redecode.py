"""`ss-track import --redecode`: re-seal an imported source under the installed decode policy.

A source record states the policy that produced it, so a new policy revision strands every one
that predates it: `corpus build` refuses the old record with `DECODE_POLICY_MISMATCH`, and a plain
re-import refuses the bytes as `IMPORT_CONFLICT` because the installed decoder now disagrees with
what is stored. `--redecode` decodes the one stored copy again, under the policy installed today,
and writes the result as a successor the way an amendment does (`corpus.sources.replacement`).

Terms are never invented. A plain `--redecode` carries the existing rights and sensitivity forward
unchanged, exactly as they were recorded; only `--amend-terms` given alongside it takes them from the
declaration, which is the one case a record too old for `--amend-terms` alone can still reach the
current major, because a decode and a declared term arrive together.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.refusal import JsonValue, RefusalCode
from ss_track.corpus.declarations.declaration import (
    RecordingDeclaration,
    load_recording_declaration,
)
from ss_track.corpus.decoding.decode import inspect_media
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.decoding.streams import selected_video_index
from ss_track.corpus.sources.amendment import capture_changes
from ss_track.corpus.sources.identity import require_stored_source, source_identity
from ss_track.corpus.sources.replacement import (
    ExistingRecord,
    ReplacementResult,
    replace_record,
    replacing_source,
    require_migration_operations,
    require_unchanged_facts,
    successor_of,
)
from ss_track.corpus.sources.source_file import declared_content_hash
from ss_track.corpus.sources.source_record import declared_terms, decoded_sequence
from ss_track.corpus.sources.terms import TERM_SECTIONS
from ss_track.corpus.sources.timestamps import assess_timestamps

REDECODED = "redecoded"
_NOT_IMPORTED = "no imported source has these bytes, and a redecode cannot import a file"


def redecode_source(
    declaration_path: Path,
    data_root: Path,
    *,
    amend_terms: bool = False,
    amend_capture: bool = False,
) -> ReplacementResult:
    """Decode one imported source's stored bytes again, and re-seal it under one atomic replace."""
    declaration = load_recording_declaration(declaration_path)
    sha256 = source_identity(declared_content_hash(declaration), _index_for_redecode(declaration))
    with replacing_source(data_root, sha256, _NOT_IMPORTED) as existing:
        require_migration_operations(
            existing, sha256, amend_capture=amend_capture, amend_terms=amend_terms, redecode=True
        )
        require_unchanged_facts(existing.record, declaration, sha256, amend_capture=amend_capture)
        terms = declared_terms(declaration) if amend_terms else _carried_terms(existing.record)
        capture = capture_changes(existing.record, declaration) if amend_capture else {}
        successor = successor_of(
            existing, _redecoded(existing, declaration) | terms | capture, sha256
        )
        return replace_record(
            REDECODED, existing, successor, sha256, data_root, policy_current=True
        )


def _redecoded(existing: ExistingRecord, declaration: RecordingDeclaration) -> dict[str, JsonValue]:
    """Decode the stored bytes under the installed policy, keeping the declared clock evidence."""
    record = existing.record
    directory = existing.path.parent
    stored = require_stored_source(directory, record, mismatch=RefusalCode.SOURCE_HASH_MISMATCH)
    policy = current_decode_policy()
    inspection = inspect_media(stored, policy, video_stream_index=declaration.video_stream_index)
    clock_evidence = record["sequence"]["capture_clock_evidence"]
    quality = assess_timestamps(inspection.pts, clock_evidence)
    sequence = decoded_sequence(inspection, quality, clock_evidence, declaration.color_matrix)
    return {"sequence": sequence, **policy.record_fields()}


def _index_for_redecode(declaration: RecordingDeclaration) -> int:
    """Return the stream this redecode addresses.

    An omitted index on a file that is still present opens the container and refuses an unnamed
    choice, so a later stream is not rewritten as the first. After the file is gone, an omitted
    index addresses the first stream and the declaration's hash.
    """
    declared = declaration.video_stream_index
    if declared is not None:
        return declared
    path = declaration.source_path
    if path.is_file():
        return selected_video_index(path, current_decode_policy().format_options, None)
    return 0


def _carried_terms(existing: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Return the existing rights and sensitivity, exactly as recorded: never invented."""
    return {section: existing.get(section, {}) for section in TERM_SECTIONS}
