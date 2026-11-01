"""Typed forms of the operator-written recording and corpus declarations."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ss_track.corpus.fields import Fields, invalid, load_yaml_mapping
from ss_track.corpus.refusal import JsonValue

CORPUS_SCHEMA_VERSION = 2
RIGHTS_BASES = frozenset({"owned", "licensed", "consented", "public_domain"})
SHARING_SCOPES = ("restricted", "public")  # narrowest first
SENSITIVITY_LEVELS = ("low", "moderate", "high")  # least sensitive first
SPLITS = ("development", "calibration", "locked")
RANGE_STATUSES = frozenset({"measured", "estimated", "unknown"})
CAPTURE_FIELDS = (
    "camera",
    "lens",
    "exposure",
    "focus",
    "fov",
    "camera_control_mode",
    "lighting",
    "background",
    "motion",
    "object_pixel_extent",
)
IDENTIFIER_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


@dataclass(frozen=True, slots=True)
class Rights:
    """What may be done with a source. Nothing here has a default."""

    holder: str
    basis: str
    retention: str
    sharing: str


@dataclass(frozen=True, slots=True)
class Sensitivity:
    """How carefully a source must be handled."""

    level: str
    notes: str | None


@dataclass(frozen=True, slots=True)
class RecordingDeclaration:
    """One operator-written `recording.yaml`."""

    source_path: Path
    expected_sha256: str | None
    rights: Rights
    sensitivity: Sensitivity
    capture_clock_evidence: str | None
    capture: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Selection:
    """A half-open frame window `[start_frame, end_frame)` over one sequence."""

    start_frame: int
    end_frame: int


@dataclass(frozen=True, slots=True)
class StreamDeclaration:
    """One sensor's recording of an encounter, taken from one imported source."""

    stream_id: str
    source_sha256: str
    selection: Selection | None


@dataclass(frozen=True, slots=True)
class EncounterDeclaration:
    """Every stream of one event in front of the sensors."""

    encounter_id: str
    streams: tuple[StreamDeclaration, ...]


@dataclass(frozen=True, slots=True)
class GroupDeclaration:
    """Related encounters that are not independent, so one split holds all of them."""

    group_id: str
    split: str
    encounters: tuple[EncounterDeclaration, ...]


@dataclass(frozen=True, slots=True)
class ScenarioRights:
    """What the corpus's scenario asks of every source. Nothing here has a default."""

    sharing: str
    max_sensitivity: str


@dataclass(frozen=True, slots=True)
class CorpusDeclaration:
    """One operator-written `corpus.yaml`."""

    corpus_id: str
    decode_policy_sha256: str | None
    scenario_rights: ScenarioRights
    groups: tuple[GroupDeclaration, ...]

    def members(self) -> Iterator[tuple[GroupDeclaration, EncounterDeclaration, StreamDeclaration]]:
        """Return every stream with the encounter and group that hold it."""
        for group in self.groups:
            for encounter in group.encounters:
                for stream in encounter.streams:
                    yield group, encounter, stream


def load_recording_declaration(path: Path) -> RecordingDeclaration:
    """Parse and validate a recording declaration."""
    with Fields(load_yaml_mapping(path), "recording") as fields:
        fields.schema_version()
        with fields.child("source") as source:
            relative_path = Path(source.text("path"))
            expected_sha256 = source.sha256("sha256") if source.has("sha256") else None
        rights = _read_rights(fields.child("rights"))
        sensitivity = _read_sensitivity(fields.child("sensitivity"))
        with fields.optional_child("timestamps") as timestamps:
            capture_clock_evidence = timestamps.optional_text("capture_clock_evidence")
        capture = _read_capture(fields.optional_child("capture"))
    return RecordingDeclaration(
        source_path=path.resolve().parent / relative_path,
        expected_sha256=expected_sha256,
        rights=rights,
        sensitivity=sensitivity,
        capture_clock_evidence=capture_clock_evidence,
        capture=capture,
    )


def load_corpus_declaration(path: Path) -> CorpusDeclaration:
    """Parse and validate a corpus declaration."""
    with Fields(load_yaml_mapping(path), "corpus") as fields:
        fields.schema_version(CORPUS_SCHEMA_VERSION)
        corpus_id = _identifier(fields, "corpus_id")
        policy_sha256 = (
            fields.sha256("decode_policy_sha256") if fields.has("decode_policy_sha256") else None
        )
        scenario_rights = _read_scenario_rights(fields.child("scenario_rights"))
        groups = tuple(
            _read_group(raw, f"corpus.groups[{position}]")
            for position, raw in enumerate(fields.items("groups"))
        )
    return CorpusDeclaration(corpus_id, policy_sha256, scenario_rights, groups)


def _identifier(fields: Fields, key: str) -> str:
    value = fields.text(key)
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise invalid(f"{key} must match {IDENTIFIER_PATTERN.pattern}")
    return value


def _read_rights(fields: Fields) -> Rights:
    with fields:
        return Rights(
            holder=fields.text("holder"),
            basis=fields.choice("basis", RIGHTS_BASES),
            retention=fields.text("retention"),
            sharing=fields.choice("sharing", SHARING_SCOPES),
        )


def _read_sensitivity(fields: Fields) -> Sensitivity:
    with fields:
        return Sensitivity(
            level=fields.choice("level", SENSITIVITY_LEVELS),
            notes=fields.optional_text("notes"),
        )


def _read_capture(fields: Fields) -> dict[str, JsonValue]:
    with fields:
        capture: dict[str, JsonValue] = {name: fields.scalar(name) for name in CAPTURE_FIELDS}
        capture["range"] = _read_range(fields.optional_child("range"))
    return capture


def _read_range(fields: Fields) -> dict[str, JsonValue]:
    with fields:
        status = fields.choice("status", RANGE_STATUSES) if fields.has("status") else "unknown"
        value_m = fields.scalar("value_m")
        method = fields.optional_text("method")
    if status != "unknown" and (value_m is None or method is None):
        raise invalid(f"capture.range.status {status} requires value_m and method")
    if status == "unknown" and (value_m is not None or method is not None):
        raise invalid("capture.range.status unknown cannot carry value_m or method")
    return {"status": status, "value_m": value_m, "method": method}


def _read_scenario_rights(fields: Fields) -> ScenarioRights:
    with fields:
        return ScenarioRights(
            sharing=fields.choice("sharing", SHARING_SCOPES),
            max_sensitivity=fields.choice("max_sensitivity", SENSITIVITY_LEVELS),
        )


def _read_group(raw: object, where: str) -> GroupDeclaration:
    with Fields(raw, where) as fields:
        group_id = _identifier(fields, "group_id")
        split = fields.choice("split", SPLITS)
        encounters = tuple(
            _read_encounter(item, f"{where}.encounters[{position}]")
            for position, item in enumerate(fields.items("encounters"))
        )
    return GroupDeclaration(group_id, split, encounters)


def _read_encounter(raw: object, where: str) -> EncounterDeclaration:
    with Fields(raw, where) as fields:
        encounter_id = _identifier(fields, "encounter_id")
        streams = tuple(
            _read_stream(item, f"{where}.streams[{position}]")
            for position, item in enumerate(fields.items("streams"))
        )
    return EncounterDeclaration(encounter_id, streams)


def _read_stream(raw: object, where: str) -> StreamDeclaration:
    with Fields(raw, where) as fields:
        stream_id = _identifier(fields, "stream_id")
        source_sha256 = fields.sha256("source_sha256")
        selection = _read_selection(fields, where) if fields.has("selection") else None
    return StreamDeclaration(stream_id, source_sha256, selection)


def _read_selection(fields: Fields, where: str) -> Selection:
    with fields.child("selection") as window:
        selection = Selection(window.index("start_frame"), window.index("end_frame"))
    if selection.start_frame >= selection.end_frame:
        raise invalid(f"{where}.selection must have start_frame before end_frame")
    return selection
