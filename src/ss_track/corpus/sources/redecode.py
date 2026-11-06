"""`ss-track import --redecode`: re-seal an imported source under the installed decode policy.

A source record states the policy that produced it, so a new policy revision strands every one
that predates it: `corpus build` refuses the old record with `DECODE_POLICY_MISMATCH`, and a plain
re-import refuses the bytes as `IMPORT_CONFLICT` because the installed decoder now disagrees with
what is stored. `--redecode` decodes the one stored copy again, under the policy installed today,
and writes the result as a new record the same way an amendment does: under the shared source lock,
keeping the replaced record beside it. A replacement lists the corpus versions on this data root
that pin the record it replaced, and that listing never fails the redecode.

Terms are never invented. A plain `--redecode` carries the existing rights and sensitivity forward
unchanged, exactly as they were recorded; only `--amend-terms` given alongside it takes them from the
declaration, which is the one case a record too old for `--amend-terms` alone can still reach the
current major, because a decode and a declared term arrive together.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.declaration import (
    RecordingDeclaration,
    load_recording_declaration,
)
from ss_track.corpus.decoding.declared_color import apply_declared_color
from ss_track.corpus.decoding.decode import inspect_media
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.decoding.streams import selected_video_index
from ss_track.corpus.records.sealed import read_sealed, read_stated
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.sources.amendment import (
    UNCHANGED,
    AmendmentResult,
    content_hash,
    exclusive_source_lock,
    keep_replaced,
    require_current_facts,
    require_unchanged_facts,
)
from ss_track.corpus.sources.identity import require_stored_source, source_identity
from ss_track.corpus.sources.importer import (
    MANIFEST_NAME,
    SOURCE_MANIFEST,
    declared_terms,
    decode_policy_sha256,
    decoded_facts,
    source_directory,
)
from ss_track.corpus.sources.terms import TERM_SECTIONS, changed_terms
from ss_track.corpus.sources.timestamps import assess_timestamps
from ss_track.corpus.versions.impact import report_amendment_impact
from ss_track.schema.registry.contract import FACTS, VERSION_FIELD, VIEW

REDECODED = "redecoded"


def redecode_source(
    declaration_path: Path, data_root: Path, *, amend_terms: bool = False
) -> AmendmentResult:
    """Decode one imported source's stored bytes again, and re-seal it under one atomic replace."""
    declaration = load_recording_declaration(declaration_path)
    sha256 = source_identity(content_hash(declaration), _index_for_redecode(declaration))
    directory = source_directory(data_root, sha256)
    if not directory.is_dir():
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "no imported source has these bytes, and a redecode cannot import a file",
            {"source_sha256": sha256},
        )
    with exclusive_source_lock(data_root):
        return _redecode(declaration, sha256, directory, data_root, amend_terms=amend_terms)


def _redecode(
    declaration: RecordingDeclaration,
    sha256: str,
    directory: Path,
    data_root: Path,
    *,
    amend_terms: bool,
) -> AmendmentResult:
    path = directory / MANIFEST_NAME
    stated = read_stated(path, SOURCE_MANIFEST)
    # A view major reads as the current one; a `facts` major is what a redecode writes forward too.
    existing: Mapping[str, Any] = (
        read_sealed(path, SOURCE_MANIFEST) if stated.disposition == VIEW else stated.record
    )
    require_unchanged_facts(existing, declaration, sha256)
    stored = require_stored_source(directory, existing, mismatch=RefusalCode.SOURCE_HASH_MISMATCH)
    policy = current_decode_policy()
    inspection = inspect_media(stored, policy, video_stream_index=declaration.video_stream_index)
    clock_evidence = existing["sequence"]["capture_clock_evidence"]
    quality = assess_timestamps(inspection.pts, clock_evidence)
    policy_record = policy.as_record()
    sequence = decoded_facts(inspection)
    sequence["frame_count"] = len(inspection.pts)
    sequence["timestamp_quality"] = quality
    sequence["capture_clock_evidence"] = clock_evidence
    apply_declared_color(sequence, inspection.source_pixel_format, declaration.color_matrix)
    carried = {key: value for key, value in existing.items() if key != SEAL_FIELD}
    terms = declared_terms(declaration) if amend_terms else _carried_terms(existing)
    successor = (
        carried
        | {
            VERSION_FIELD: SOURCE_MANIFEST.major,
            "sequence": sequence,
            "decode_policy": policy_record,
            "decode_policy_sha256": decode_policy_sha256(policy_record),
        }
        | terms
    )
    if stated.disposition == FACTS:
        require_current_facts(successor, existing, sha256, path)
    sealed = seal(successor)
    if sealed == existing:
        seal_value = str(sealed[SEAL_FIELD])
        return AmendmentResult(UNCHANGED, sha256, seal_value, path, None, None, [], True)
    replaced_sha = str(existing[SEAL_FIELD])
    replaced = keep_replaced(existing, directory)
    write_sealed(path, sealed)
    return AmendmentResult(
        status=REDECODED,
        source_sha256=sha256,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=path,
        replaced_manifest_sha256=replaced_sha,
        replaced_path=replaced,
        changed_terms=changed_terms(existing, sealed),
        decode_policy_current=True,
        impact=report_amendment_impact(data_root, replaced_sha),
    )


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
