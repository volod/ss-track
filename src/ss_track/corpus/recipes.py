"""Generated-case recipes: their strict declaration and the record a corpus version stores.

A recipe has no split, encounter or group to declare, because it sits under its parent stream and
inherits all three. That is what keeps a case from ever becoming a new encounter.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ss_track.corpus.case_model import Pixels
from ss_track.corpus.fields import Fields, Selection, invalid
from ss_track.corpus.refusal import JsonValue
from ss_track.corpus.transforms import TRANSFORM_REVISIONS, prepare_case

MAX_SEED = 2**63 - 1
MAX_SPRITES = 256
MAX_NOISE = 255

type _Reader = Callable[[Fields, str], JsonValue]


@dataclass(frozen=True, slots=True)
class CaseRecipe:
    """One operator-declared generated case of a parent stream."""

    case_id: str
    transform: str
    seed: int
    window: Selection | None
    parameters: dict[str, JsonValue]


def _at_most(limit: int, value: int, fields: Fields, key: str) -> int:
    if value > limit:
        raise invalid(f"{fields.where}.{key} must be at most {limit}")
    return value


def _positive(fields: Fields, key: str) -> int:
    value = fields.index(key)
    if value < 1:
        raise invalid(f"{fields.where}.{key} must be at least 1")
    return value


def _noise(fields: Fields, key: str) -> int:
    return _at_most(MAX_NOISE, fields.index(key), fields, key)


def _sprite_count(fields: Fields, key: str) -> int:
    return _at_most(MAX_SPRITES, _positive(fields, key), fields, key)


def _region(fields: Fields, key: str) -> JsonValue:
    with fields.child(key) as region:
        return {
            "x": region.index("x"),
            "y": region.index("y"),
            "width": _positive(region, "width"),
            "height": _positive(region, "height"),
        }


_PARAMETERS: dict[str, dict[str, _Reader]] = {
    "target_absence": {"region": _region, "plate_frame": Fields.index, "noise": _noise},
    "moving_background": {
        "region": _region,
        "sprite_count": _sprite_count,
        "sprite_size": _positive,
        "max_speed": _positive,
    },
    "camera_shake": {"amplitude": _positive},
    "blur": {"max_radius": _positive},
    "dropped_frames": {"count": _positive},
    "duplicated_frames": {"count": _positive},
    "short_occlusion": {"region": _region},
}


def read_recipe(raw: object, where: str) -> CaseRecipe:
    """Parse one recipe, reading parameters under the rules of its transform."""
    with Fields(raw, where) as fields:
        case_id = fields.identifier("case_id")
        transform = fields.choice("transform", _PARAMETERS.keys())
        seed = _at_most(MAX_SEED, fields.index("seed"), fields, "seed")
        window = fields.selection("window") if fields.has("window") else None
        with fields.child("parameters") as declared:
            parameters = {
                name: read(declared, name) for name, read in _PARAMETERS[transform].items()
            }
    return CaseRecipe(case_id, transform, seed, window, parameters)


def _case_record(recipe: CaseRecipe, stream: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Return a case's record, with its membership copied from its parent and no other origin."""
    selection = stream["selection"]
    window = recipe.window
    return {
        "case_id": recipe.case_id,
        "parent_stream_id": stream["stream_id"],
        "encounter_id": stream["encounter_id"],
        "group_id": stream["group_id"],
        "split": stream["split"],
        "source_sha256": stream["source_sha256"],
        "transform": recipe.transform,
        "transform_revision": TRANSFORM_REVISIONS[recipe.transform],
        "seed": recipe.seed,
        "window": selection
        if window is None
        else {"start_frame": window.start_frame, "end_frame": window.end_frame},
        "parameters": recipe.parameters,
    }


def _no_pixels_at_build(frame_index: int) -> Pixels:
    """A build has no staged frames, and a transform reads frames only while painting."""
    raise AssertionError(f"a transform read frame {frame_index} during a build")


def case_records(
    recipes: Sequence[tuple[str, CaseRecipe]], streams: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Validate each recipe against its parent, then return records ordered by `case_id`."""
    parents = {stream["stream_id"]: stream for stream in streams}
    records = []
    for parent_stream_id, recipe in recipes:
        parent = parents[parent_stream_id]
        record = _case_record(recipe, parent)
        selection = range(parent["selection"]["start_frame"], parent["selection"]["end_frame"])
        rendering = prepare_case(
            record, selection, parent["width"], parent["height"], _no_pixels_at_build
        )
        records.append(record | {"label_transform": rendering.label_transform})
    return sorted(records, key=lambda record: str(record["case_id"]))
