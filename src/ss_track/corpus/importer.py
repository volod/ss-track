"""`ss-track import`: turn one declared recording into an immutable, hashed source record."""

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from ss_track.corpus.declaration import (
    RECORDING_SCHEMA_VERSION,
    RecordingDeclaration,
    load_recording_declaration,
)
from ss_track.corpus.decode import (
    DecodePolicy,
    MediaInspection,
    current_decode_policy,
    inspect_media,
)
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import (
    READ_ONLY_FILE_MODE,
    SEAL_FIELD,
    canonical_json,
    copy_with_sha256,
    read_sealed,
    seal,
    sha256_bytes,
    sha256_file,
    write_sealed,
)
from ss_track.corpus.timestamps import assess_timestamps

SOURCE_MANIFEST_KIND = "ss-track.source-manifest"
SCHEMA_VERSION = RECORDING_SCHEMA_VERSION
IMPORT_DIRECTORY = "import"
MANIFEST_NAME = "manifest.json"
_SOURCE_STEM = "source"

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Outcome of an accepted import."""

    status: str
    source_sha256: str
    manifest_sha256: str
    manifest_path: Path
    timestamp_quality: str
    frame_count: int
    completeness_checks: list[str]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        record: dict[str, JsonValue] = asdict(self)
        record["manifest_path"] = str(self.manifest_path)
        return record


def source_directory(data_root: Path, source_sha256: str) -> Path:
    """Return the content-addressed home of one imported source."""
    return data_root / IMPORT_DIRECTORY / source_sha256


def decode_policy_sha256(policy_record: dict[str, JsonValue]) -> str:
    """Return the hash that identifies a decode policy."""
    return sha256_bytes(canonical_json(policy_record))


def decoded_facts(inspection: MediaInspection) -> dict[str, JsonValue]:
    """Return what a decode established, in the form a source manifest stores it."""
    facts: dict[str, JsonValue] = asdict(inspection)
    facts["pts"] = list(inspection.pts)
    facts["completeness_checks"] = list(inspection.completeness_checks)
    return facts


def import_source(declaration_path: Path, data_root: Path) -> ImportResult:
    """Import one recording, leaving a complete record or nothing."""
    declaration = load_recording_declaration(declaration_path)
    _require_regular_file(declaration.source_path)
    if declaration.source_path.stat().st_size == 0:
        raise CorpusRefusal(RefusalCode.SOURCE_EMPTY, "source file has zero length")
    policy = current_decode_policy()
    imports = data_root / IMPORT_DIRECTORY
    imports.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".incoming-", dir=imports) as scratch:
        staged = Path(scratch) / "staged"
        staged.mkdir()
        return _import_into(declaration, policy, staged, data_root)


def _require_regular_file(path: Path) -> None:
    if not path.exists():
        raise CorpusRefusal(RefusalCode.SOURCE_NOT_FOUND, f"source file not found: {path.name}")
    if not path.is_file():
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, f"not a regular file: {path.name}")


def _copy_source(declaration: RecordingDeclaration, stored: Path) -> tuple[str, int]:
    """Copy first, so the hash and the decode describe exactly the bytes that are retained."""
    try:
        return copy_with_sha256(declaration.source_path, stored)
    except PermissionError as error:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, str(error.strerror)) from error


def _import_into(
    declaration: RecordingDeclaration, policy: DecodePolicy, staged: Path, data_root: Path
) -> ImportResult:
    stored = staged / f"{_SOURCE_STEM}{declaration.source_path.suffix.lower()}"
    sha256, size = _copy_source(declaration, stored)
    expected = declaration.expected_sha256
    if expected is not None and expected != sha256:
        raise CorpusRefusal(
            RefusalCode.SOURCE_HASH_MISMATCH,
            "source bytes do not match the declared hash",
            {"expected_sha256": expected, "actual_sha256": sha256},
        )
    inspection = inspect_media(stored, policy)
    quality = assess_timestamps(inspection.pts, declaration.capture_clock_evidence)
    if not inspection.completeness_checks:
        _LOG.warning("source %s has no container-level completeness evidence", sha256)
    sealed = seal(_manifest_body(declaration, policy, inspection, quality, sha256, size, stored))
    write_sealed(staged / MANIFEST_NAME, sealed)
    stored.chmod(READ_ONLY_FILE_MODE)
    target = source_directory(data_root, sha256)
    status = _commit(staged, target, sealed, stored.name)
    return ImportResult(
        status=status,
        source_sha256=sha256,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=target / MANIFEST_NAME,
        timestamp_quality=quality.value,
        frame_count=len(inspection.pts),
        completeness_checks=list(inspection.completeness_checks),
    )


def _manifest_body(
    declaration: RecordingDeclaration,
    policy: DecodePolicy,
    inspection: MediaInspection,
    quality: str,
    sha256: str,
    size: int,
    stored: Path,
) -> dict[str, JsonValue]:
    """Build the hashed record. It holds no clock time or path, so an import can be repeated."""
    policy_record = policy.as_record()
    sequence = decoded_facts(inspection)
    sequence["frame_count"] = len(inspection.pts)
    sequence["timestamp_quality"] = quality
    sequence["capture_clock_evidence"] = declaration.capture_clock_evidence
    return {
        "kind": SOURCE_MANIFEST_KIND,
        "schema_version": SCHEMA_VERSION,
        "source": {
            "sha256": sha256,
            "sha256_declared": declaration.expected_sha256 is not None,
            "size_bytes": size,
            "stored_name": stored.name,
        },
        "rights": dict(asdict(declaration.rights)),
        "sensitivity": dict(asdict(declaration.sensitivity)),
        "capture": declaration.capture,
        "sequence": sequence,
        "decode_policy": policy_record,
        "decode_policy_sha256": decode_policy_sha256(policy_record),
    }


def _commit(staged: Path, target: Path, sealed: dict[str, JsonValue], stored_name: str) -> str:
    """Publish a finished directory in one rename, or confirm the one already there."""
    if not target.exists():
        staged.rename(target)
        return "imported"
    existing = read_sealed(target / MANIFEST_NAME, SOURCE_MANIFEST_KIND)
    if existing != sealed:
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "this source was already imported with a different declaration or decoder",
            {
                "existing_manifest_sha256": existing[SEAL_FIELD],
                "new_manifest_sha256": sealed[SEAL_FIELD],
            },
        )
    if sha256_file(target / stored_name) != target.name:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "the stored source no longer matches its hash",
            {"source_sha256": target.name},
        )
    return "unchanged"
