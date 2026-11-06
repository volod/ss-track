"""Generated-case recipes: their strict declaration and the record a corpus version stores.

A recipe has no split, encounter or group to declare, because it sits under its parent stream and
inherits all three. That is what keeps a case from ever becoming a new encounter.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.cases.case_model import Pixels
from ss_track.corpus.cases.transforms import TRANSFORM_REVISIONS, prepare_case
from ss_track.corpus.declarations.fields import Fields, Selection


@dataclass(frozen=True, slots=True)
class CaseRecipe:
    """One operator-declared generated case of a parent stream."""

    case_id: str
    transform: str
    seed: int
    window: Selection | None
    parameters: dict[str, JsonValue]


def read_recipe(raw: object, where: str) -> CaseRecipe:
    """Read one recipe, whose contract branch for its transform stated every parameter and bound."""
    fields = Fields(raw, where)
    return CaseRecipe(
        fields.text("case_id"),
        fields.text("transform"),
        fields.index("seed"),
        fields.optional_selection("window"),
        fields.mapping("parameters"),
    )


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
            record,
            selection,
            parent["width"],
            parent["height"],
            _no_pixels_at_build,
            timestamp_quality=parent["timestamp_quality"],
        )
        records.append(record | {"label_transform": rendering.label_transform})
    return sorted(records, key=lambda record: str(record["case_id"]))
