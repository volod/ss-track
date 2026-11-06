"""Typed forms of the operator-written recording and corpus declarations."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import JsonValue
from ss_track.corpus.cases.recipes import CaseRecipe, read_recipe
from ss_track.corpus.declarations.fields import Fields, Selection, invalid
from ss_track.corpus.decoding.declared_color import matrix_code
from ss_track.schema.validation.enforce import read_declaration

RECORDING_CONTRACT = "declaration/recording"
CORPUS_CONTRACT = "declaration/corpus"
RECORDING_SCHEMA_VERSION = 2
CORPUS_SCHEMA_VERSION = 3
# Orders the contracts do not state, which the rights checks compare by.
SHARING_SCOPES = ("restricted", "public")  # narrowest first
SENSITIVITY_LEVELS = ("low", "moderate", "high")  # least sensitive first
UNKNOWN_RANGE = "unknown"
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


@dataclass(frozen=True, slots=True)
class Rights:
    """What may be done with a source. Nothing here has a default."""

    holder: str
    basis: str
    retention: str
    retain_until: str | None
    derived_frames: bool
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
    video_stream_index: int | None
    color_matrix: int | None
    rights: Rights
    sensitivity: Sensitivity
    capture_clock_evidence: str | None
    capture: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class StreamDeclaration:
    """One sensor's recording of an encounter, taken from one imported source."""

    stream_id: str
    source_sha256: str
    selection: Selection | None
    generated_cases: tuple[CaseRecipe, ...]


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
    supersedes: str | None
    scenario_rights: ScenarioRights
    groups: tuple[GroupDeclaration, ...]

    def members(self) -> Iterator[tuple[GroupDeclaration, EncounterDeclaration, StreamDeclaration]]:
        """Return every stream with the encounter and group that hold it."""
        for group in self.groups:
            for encounter in group.encounters:
                for stream in encounter.streams:
                    yield group, encounter, stream

    def recipes(self) -> Iterator[tuple[str, CaseRecipe]]:
        """Return every generated case with the `stream_id` of its parent."""
        for _, _, stream in self.members():
            for recipe in stream.generated_cases:
                yield stream.stream_id, recipe


def load_recording_declaration(path: Path) -> RecordingDeclaration:
    """Parse a recording declaration that its contract validated in full."""
    fields = Fields(
        read_declaration(path, RECORDING_CONTRACT, RECORDING_SCHEMA_VERSION), "recording"
    )
    source = fields.child("source")
    expected_sha256 = source.text("sha256") if source.has("sha256") else None
    timestamps = fields.optional_child("timestamps")
    return RecordingDeclaration(
        source_path=path.resolve().parent / source.text("path"),
        expected_sha256=expected_sha256,
        video_stream_index=(
            source.index("video_stream_index") if source.has("video_stream_index") else None
        ),
        color_matrix=_color_matrix(fields),
        rights=_read_rights(fields.child("rights")),
        sensitivity=_read_sensitivity(fields.child("sensitivity")),
        capture_clock_evidence=timestamps.optional_text("capture_clock_evidence"),
        capture=_read_capture(fields.optional_child("capture")),
    )


def load_corpus_declaration(path: Path) -> CorpusDeclaration:
    """Parse a corpus declaration that its contract validated in full."""
    fields = Fields(read_declaration(path, CORPUS_CONTRACT, CORPUS_SCHEMA_VERSION), "corpus")
    corpus_id = fields.text("corpus_id")
    supersedes = fields.optional_text("supersedes")
    if supersedes == corpus_id:
        raise invalid(f"corpus {corpus_id} cannot supersede itself")
    groups = tuple(
        _read_group(raw, f"corpus.groups[{position}]")
        for position, raw in enumerate(fields.items("groups"))
    )
    return CorpusDeclaration(
        corpus_id,
        fields.optional_text("decode_policy_sha256"),
        supersedes,
        _read_scenario_rights(fields.child("scenario_rights")),
        groups,
    )


def _color_matrix(fields: Fields) -> int | None:
    if not fields.has("color"):
        return None
    return matrix_code(fields.child("color").text("matrix"))


def _read_rights(fields: Fields) -> Rights:
    return Rights(
        holder=fields.text("holder"),
        basis=fields.text("basis"),
        retention=fields.text("retention"),
        retain_until=fields.nullable_date("retain_until"),
        derived_frames=fields.boolean("derived_frames"),
        sharing=fields.text("sharing"),
    )


def _read_sensitivity(fields: Fields) -> Sensitivity:
    return Sensitivity(level=fields.text("level"), notes=fields.optional_text("notes"))


def _read_capture(fields: Fields) -> dict[str, JsonValue]:
    capture: dict[str, JsonValue] = {name: fields.scalar(name) for name in CAPTURE_FIELDS}
    capture["range"] = _read_range(fields.optional_child("range"))
    return capture


def _read_range(fields: Fields) -> dict[str, JsonValue]:
    """Apply the contract's range rule, which states that an absent status is unknown."""
    status = fields.text("status") if fields.has("status") else UNKNOWN_RANGE
    value_m = fields.scalar("value_m")
    method = fields.optional_text("method")
    if status != UNKNOWN_RANGE and (value_m is None or method is None):
        raise invalid(f"capture.range.status {status} requires value_m and method")
    if status == UNKNOWN_RANGE and (value_m is not None or method is not None):
        raise invalid("capture.range.status unknown cannot carry value_m or method")
    return {"status": status, "value_m": value_m, "method": method}


def _read_scenario_rights(fields: Fields) -> ScenarioRights:
    return ScenarioRights(
        sharing=fields.text("sharing"), max_sensitivity=fields.text("max_sensitivity")
    )


def _read_group(raw: object, where: str) -> GroupDeclaration:
    fields = Fields(raw, where)
    encounters = tuple(
        _read_encounter(item, f"{where}.encounters[{position}]")
        for position, item in enumerate(fields.items("encounters"))
    )
    return GroupDeclaration(fields.text("group_id"), fields.text("split"), encounters)


def _read_encounter(raw: object, where: str) -> EncounterDeclaration:
    fields = Fields(raw, where)
    streams = tuple(
        _read_stream(item, f"{where}.streams[{position}]")
        for position, item in enumerate(fields.items("streams"))
    )
    return EncounterDeclaration(fields.text("encounter_id"), streams)


def _read_stream(raw: object, where: str) -> StreamDeclaration:
    fields = Fields(raw, where)
    generated_cases = tuple(
        read_recipe(item, f"{where}.generated_cases[{position}]")
        for position, item in enumerate(fields.optional_items("generated_cases"))
    )
    return StreamDeclaration(
        fields.text("stream_id"),
        fields.text("source_sha256"),
        fields.optional_selection("selection"),
        generated_cases,
    )
