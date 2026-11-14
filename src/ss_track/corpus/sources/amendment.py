"""Record explicit terms or capture judgments for an imported source, decoding nothing.

Only explicitly requested terms or capture judgments change. Other facts are carried from the
existing record, so restoring a current record's prior values restores its seal. Stored bytes are not read: a
withdrawal must stay recordable after an operator has already removed them, and `corpus build`
hashes them again regardless. The installed decoder is not consulted either, because recording
narrower terms must not need a decode of the material they withdraw. The successor is written as
`corpus.sources.replacement` states, which `--redecode` shares.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.declaration import (
    RecordingDeclaration,
    load_recording_declaration,
)
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.sources.identity import addressed_identity
from ss_track.corpus.sources.replacement import (
    ReplacementResult,
    replace_record,
    replacing_source,
    require_migration_operations,
    require_unchanged_facts,
    successor_of,
)
from ss_track.corpus.sources.source_file import declared_content_hash
from ss_track.corpus.sources.source_record import declared_terms

AMENDED = "amended"
_NOT_IMPORTED = (
    "no imported source has these bytes, and an amendment cannot import or change a file"
)


def amend_source_terms(
    declaration_path: Path,
    data_root: Path,
    *,
    amend_capture: bool = False,
    amend_terms: bool = True,
) -> ReplacementResult:
    """Replace the requested source facts atomically, keeping the record it replaces."""
    declaration = load_recording_declaration(declaration_path)
    sha256 = named_source(declaration)
    with replacing_source(data_root, sha256, _NOT_IMPORTED) as existing:
        require_migration_operations(
            existing, sha256, amend_capture=amend_capture, amend_terms=amend_terms, redecode=False
        )
        require_unchanged_facts(existing.record, declaration, sha256, amend_capture=amend_capture)
        changes = declared_terms(declaration) if amend_terms else {}
        if amend_capture:
            changes.update(capture_changes(existing.record, declaration))
        successor = successor_of(existing, changes, sha256)
        current = _policy_is_installed(existing.record)
        return replace_record(
            AMENDED, existing, successor, sha256, data_root, policy_current=current
        )


def named_source(declaration: RecordingDeclaration) -> str:
    """Return the source identity this declaration names.

    A later stream keeps its index, including after the file is gone, when the declared hash and
    that index together name it. An amendment does not open the container, so it cannot tell a
    missing index from the first stream.
    """
    return addressed_identity(declared_content_hash(declaration), declaration.video_stream_index)


def _policy_is_installed(record: Mapping[str, Any]) -> bool:
    return bool(record.get("decode_policy_sha256") == current_decode_policy().sha256())


def capture_changes(
    record: Mapping[str, Any], declaration: RecordingDeclaration
) -> dict[str, JsonValue]:
    """Replace only the explicit capture judgments, retaining every other capture fact."""
    capture = dict(record["capture"])
    for name in ("camera_control_mode", "observer_platform"):
        capture[name] = declaration.capture[name]
    return {"capture": capture}
