"""`ss-track corpus build`: bind imported sources into one immutable, hashed corpus version."""

from dataclasses import dataclass
from pathlib import Path

from ss_track.corpus.declaration import (
    IDENTIFIER_PATTERN,
    CorpusDeclaration,
    SequenceDeclaration,
    load_corpus_declaration,
)
from ss_track.corpus.decode import current_decode_policy
from ss_track.corpus.importer import (
    MANIFEST_NAME,
    SCHEMA_VERSION,
    SOURCE_MANIFEST_KIND,
    decode_policy_sha256,
    source_directory,
)
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import SEAL_FIELD, read_sealed, seal, sha256_file, write_sealed

CORPUS_MANIFEST_KIND = "ss-track.corpus-manifest"
CORPUS_DIRECTORY = "corpus"


@dataclass(frozen=True, slots=True)
class BuildResult:
    """Outcome of an accepted corpus build."""

    status: str
    corpus_id: str
    manifest_sha256: str
    manifest_path: Path
    sequence_count: int

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": self.status,
            "corpus_id": self.corpus_id,
            "manifest_sha256": self.manifest_sha256,
            "manifest_path": str(self.manifest_path),
            "sequence_count": self.sequence_count,
        }


def load_corpus_manifest(corpus_id: str, data_root: Path) -> dict[str, JsonValue]:
    """Read one built corpus version, refusing an identifier that cannot name one."""
    path = data_root / CORPUS_DIRECTORY / corpus_id / MANIFEST_NAME
    if not IDENTIFIER_PATTERN.fullmatch(corpus_id) or not path.is_file():
        raise CorpusRefusal(
            RefusalCode.CORPUS_NOT_BUILT, "no such corpus version", {"corpus_id": corpus_id}
        )
    return read_sealed(path, CORPUS_MANIFEST_KIND)


def build_corpus(declaration_path: Path, data_root: Path) -> BuildResult:
    """Verify every declared source again, then write the corpus version."""
    declaration = load_corpus_declaration(declaration_path)
    policy_record = current_decode_policy().as_record()
    policy_sha256 = decode_policy_sha256(policy_record)
    require_policy(declaration.decode_policy_sha256, policy_sha256, "corpus declaration")
    sequences: list[JsonValue] = [
        _sequence_record(sequence, data_root, policy_sha256)
        for sequence in sorted(declaration.sequences, key=lambda item: item.sequence_id)
    ]
    sealed = seal(_corpus_body(declaration, policy_record, policy_sha256, sequences))
    target = data_root / CORPUS_DIRECTORY / declaration.corpus_id / MANIFEST_NAME
    status = _commit(target, sealed)
    return BuildResult(
        status=status,
        corpus_id=declaration.corpus_id,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=target,
        sequence_count=len(sequences),
    )


def _corpus_body(
    declaration: CorpusDeclaration,
    policy_record: dict[str, JsonValue],
    policy_sha256: str,
    sequences: list[JsonValue],
) -> dict[str, JsonValue]:
    return {
        "kind": CORPUS_MANIFEST_KIND,
        "schema_version": SCHEMA_VERSION,
        "corpus_id": declaration.corpus_id,
        "decode_policy": policy_record,
        "decode_policy_sha256": policy_sha256,
        "sequences": sequences,
    }


def require_policy(found: JsonValue, expected: str, origin: str) -> None:
    """Refuse a source decoded under anything but the corpus's one canonical policy."""
    if found is not None and found != expected:
        raise CorpusRefusal(
            RefusalCode.DECODE_POLICY_MISMATCH,
            f"{origin} uses a different decode policy than the installed decoder",
            {"found_decode_policy_sha256": found, "installed_decode_policy_sha256": expected},
        )


def load_verified_source(source_sha256: str, data_root: Path) -> dict[str, JsonValue]:
    """Load a source record only if both the record and the stored bytes are still intact."""
    directory = source_directory(data_root, source_sha256)
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise CorpusRefusal(
            RefusalCode.SOURCE_NOT_IMPORTED,
            "the corpus names a source that has not been imported",
            {"source_sha256": source_sha256},
        )
    manifest = read_sealed(manifest_path, SOURCE_MANIFEST_KIND)
    source = manifest["source"]
    if not isinstance(source, dict):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "source record has no source section")
    stored = directory / str(source["stored_name"])
    if not stored.is_file() or sha256_file(stored) != source_sha256:
        raise CorpusRefusal(
            RefusalCode.SOURCE_HASH_MISMATCH,
            "stored source bytes do not match the imported hash",
            {"source_sha256": source_sha256},
        )
    return manifest


def _resolve_selection(sequence: SequenceDeclaration, frame_count: int) -> dict[str, JsonValue]:
    """Return the frame window, which must lie inside the decoded sequence."""
    selection = sequence.selection
    if selection is None:
        return {"start_frame": 0, "end_frame": frame_count}
    if selection.end_frame > frame_count:
        raise CorpusRefusal(
            RefusalCode.SELECTION_OUT_OF_RANGE,
            "selection runs past the end of the sequence",
            {
                "sequence_id": sequence.sequence_id,
                "start_frame": selection.start_frame,
                "end_frame": selection.end_frame,
                "frame_count": frame_count,
            },
        )
    return {"start_frame": selection.start_frame, "end_frame": selection.end_frame}


def _sequence_record(
    sequence: SequenceDeclaration, data_root: Path, policy_sha256: str
) -> dict[str, JsonValue]:
    manifest = load_verified_source(sequence.source_sha256, data_root)
    require_policy(
        manifest["decode_policy_sha256"], policy_sha256, f"source {sequence.source_sha256}"
    )
    media = manifest["sequence"]
    if not isinstance(media, dict) or not isinstance(media["frame_count"], int):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "source record has no sequence section")
    return {
        "sequence_id": sequence.sequence_id,
        "source_sha256": sequence.source_sha256,
        "source_manifest_sha256": manifest[SEAL_FIELD],
        "selection": _resolve_selection(sequence, media["frame_count"]),
        "frame_count": media["frame_count"],
        "timestamp_quality": media["timestamp_quality"],
        "completeness_checks": media["completeness_checks"],
        "rights": manifest["rights"],
        "sensitivity": manifest["sensitivity"],
    }


def _commit(target: Path, sealed: dict[str, JsonValue]) -> str:
    """A corpus version is immutable: a changed one needs a new identifier."""
    if not target.exists():
        write_sealed(target, sealed)
        return "built"
    existing = read_sealed(target, CORPUS_MANIFEST_KIND)
    if existing != sealed:
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this corpus_id already exists with different content",
            {
                "existing_manifest_sha256": existing[SEAL_FIELD],
                "new_manifest_sha256": sealed[SEAL_FIELD],
            },
        )
    return "unchanged"
