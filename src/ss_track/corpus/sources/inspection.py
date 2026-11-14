"""Read the capture facts a source record actually states, without treating them as evidence."""

from dataclasses import dataclass
from pathlib import Path

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.sealed import read_stated
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.kinds import SOURCE_MANIFEST
from ss_track.corpus.storage.layout import MANIFEST_NAME, replaced_record_path, source_directory
from ss_track.schema.validation.enforce import is_shared_type


@dataclass(frozen=True, slots=True)
class SourceInspection:
    """The original capture values and the read window's evidence disposition."""

    source_sha256: str
    manifest_sha256: str
    major: JsonValue
    disposition: str | None
    capture: dict[str, JsonValue]

    def to_record(self) -> dict[str, object]:
        """State the source facts and distinguish missing platform from the original capture."""
        return {
            "status": "inspected",
            "source_sha256": self.source_sha256,
            "manifest_sha256": self.manifest_sha256,
            "source_inspection": {
                "major": self.major,
                "disposition": self.disposition or "current",
                "capture": self.capture,
                "platform": self.capture.get("observer_platform", "unknown"),
            },
        }


def inspect_source(
    source_sha256: str, manifest_sha256: str | None, data_root: Path
) -> SourceInspection:
    """Inspect a current or retained source record, without reading its media or writing files."""
    for field, value in (("source_sha256", source_sha256), ("manifest_sha256", manifest_sha256)):
        if value is not None and not is_shared_type("sha256", value):
            raise CorpusRefusal(RefusalCode.MANIFEST_INVALID, f"invalid {field}", {field: value})
    directory = source_directory(data_root, source_sha256)
    current = directory / MANIFEST_NAME
    retained = None if manifest_sha256 is None else replaced_record_path(directory, manifest_sha256)
    path = retained if retained is not None and retained.is_file() else current
    if not path.is_file():
        raise CorpusRefusal(
            RefusalCode.SOURCE_NOT_IMPORTED,
            "source record is not kept",
            {"source_sha256": source_sha256},
        )
    stated = read_stated(path, SOURCE_MANIFEST)
    record = stated.record
    if manifest_sha256 is not None and record[SEAL_FIELD] != manifest_sha256:
        raise CorpusRefusal(
            RefusalCode.SOURCE_RECORD_CHANGED,
            "the requested source record is not kept",
            {"source_sha256": source_sha256, "source_manifest_sha256": manifest_sha256},
        )
    capture = record.get("capture")
    if not isinstance(capture, dict):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "source record has no capture section")
    return SourceInspection(
        source_sha256,
        str(record[SEAL_FIELD]),
        record.get("schema_version"),
        stated.disposition,
        capture,
    )
