"""Hand-built disagreements between two label documents."""

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from ss_track.annotate.compare import compare_label_sets
from ss_track.annotate.geometry import Box
from ss_track.annotate.label_model import (
    Instance,
    LabeledFrame,
    LabelGeometry,
    LabelSet,
    MotionEvent,
)
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.review_model import PRESENCE
from ss_track.annotate.review_values import (
    COMPARED_FIELDS,
    EVENT_FIELDS,
    FRAME_FIELDS,
    INSTANCE_FIELDS,
)
from ss_track.annotate.space import DeclaredSpace
from ss_track.schema.registry.store import load_contract_set
from tests.annotate.documents import SPACE, frame, refused, replace_frame
from tests.annotate.review_files import write_pair
from tests.schema.conftest import CONTRACTS

_BOX = '{"height":3,"width":4,"x":1,"y":2}'
_WIDER = '{"height":3,"width":5,"x":1,"y":2}'


def test_a_visibility_disagreement_is_reported_exactly(tmp_path: Path, pack: ScenarioPack) -> None:
    left, right = write_pair(
        tmp_path, pack, lambda body: replace_frame(body, frame(visibility="absent"))
    )
    rows = compare_label_sets(left, right)
    assert [
        (
            row.subject,
            row.instance_id,
            row.frame_index,
            row.event_id,
            row.field,
            row.left,
            row.right,
        )
        for row in rows
    ] == [
        ("frame", "target-1", 0, None, "geometry.box", _BOX, "null"),
        ("frame", "target-1", 0, None, "geometry.kind", '"box"', '"unlocalizable"'),
        ("frame", "target-1", 0, None, "geometry.uncertainty_px", "1.0", "null"),
        ("frame", "target-1", 0, None, "visibility", '"visible"', '"absent"'),
        ("event", None, None, "onset-1", "visibility", '"visible"', '"absent"'),
    ]


def test_a_one_pixel_box_move_is_only_that_field(tmp_path: Path, pack: ScenarioPack) -> None:
    left, right = write_pair(tmp_path, pack, _widen)
    rows = compare_label_sets(left, right)
    assert len(rows) == 1
    assert rows[0].field == "geometry.box"
    assert rows[0].left == _BOX
    assert rows[0].right == _WIDER


def test_an_integer_and_the_same_float_are_not_a_disagreement() -> None:
    left = _hand_built(1)
    right = _hand_built(1.0)
    assert compare_label_sets(left, right) == ()
    moved = compare_label_sets(left, _hand_built(2.0))
    assert [(row.field, row.left, row.right) for row in moved] == [
        ("geometry.uncertainty_px", "1", "2.0")
    ]


def test_an_added_instance_is_one_presence_row(tmp_path: Path, pack: ScenarioPack) -> None:
    def add(body: dict[str, Any]) -> None:
        extra = copy.deepcopy(body["instances"][0])
        extra["instance_id"] = "target-2"
        body["instances"].append(extra)

    _left, right = write_pair(tmp_path, pack, add)
    left, _same = write_pair(tmp_path / "same", pack, lambda _body: None)
    rows = compare_label_sets(left, right)
    assert [(row.subject, row.instance_id, row.field, row.left, row.right) for row in rows] == [
        ("instance", "target-2", PRESENCE, "false", "true")
    ]


def test_the_annotator_id_is_not_a_disagreement(tmp_path: Path, pack: ScenarioPack) -> None:
    left, right = write_pair(tmp_path, pack, lambda _body: None)
    assert compare_label_sets(left, right) == ()
    assert left.document_sha256 != right.document_sha256


def test_a_different_source_or_pack_is_refused(tmp_path: Path, pack: ScenarioPack) -> None:
    left, right = write_pair(tmp_path, pack, lambda _body: None)
    other = replace(right, space=replace(right.space, source_sha256="cd" * 32))
    refused(lambda: compare_label_sets(left, other), "different sources")
    refused(
        lambda: compare_label_sets(left, replace(right, pack_id="other-pack")), "different packs"
    )


def test_compared_fields_match_the_settlement_and_command_contracts() -> None:
    contracts = load_contract_set(CONTRACTS)
    settlement = _schema(contracts, "declaration/annotation-settlement")
    branches = settlement["$defs"]["decision"]["oneOf"]
    by_subject = {
        branch["properties"]["subject"]["const"]: set(branch["properties"]["field"]["enum"])
        for branch in branches
    }
    assert by_subject["instance"] == {PRESENCE, *INSTANCE_FIELDS}
    assert by_subject["frame"] == {PRESENCE, *FRAME_FIELDS}
    assert by_subject["event"] == {PRESENCE, *EVENT_FIELDS}
    command = _schema(contracts, "result/command")
    reported = set(command["$defs"]["label-disagreement"]["properties"]["field"]["enum"])
    assert reported == {PRESENCE, *(field for group in COMPARED_FIELDS for field in group)}
    record = _schema(contracts, "record/annotation-revision")
    assert record["properties"]["kind"]["const"] == "ss-track.annotation-revision"


def _schema(contracts: Any, name: str) -> dict[str, Any]:
    contract = contracts.named(name)
    frozen = contract.newest()
    assert frozen is not None
    schema: dict[str, Any] = contracts.frozen_schema(contract, frozen)
    return schema


def _widen(body: dict[str, Any]) -> None:
    body["instances"][0]["frames"][0]["geometry"]["box"]["width"] = 5


def _hand_built(uncertainty: int | float) -> LabelSet:
    # An integer declaration and the same float are one value. The cast keeps the int at runtime.
    geometry = LabelGeometry("box", Box(1, 2, 4, 3), None, None, cast(float, uncertainty), None)
    labeled = LabeledFrame(0, "visible", "static", "ann-a", geometry)
    instance = Instance("target-1", "bird", "reviewed", None, (labeled,))
    event = MotionEvent("onset-1", "target-1", 0, 1, "visible", "reviewed", False)
    space = DeclaredSpace(SPACE.source_sha256, SPACE.width, SPACE.height, SPACE.frame_count, 0, 90)
    return LabelSet(
        "clip-a", "aerial-small-objects", "cd" * 32, space, (instance,), (event,), "ab" * 32
    )
