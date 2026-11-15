"""The frozen label vocabulary stays the pack vocabulary, and reasons stay one list."""

from ss_track.annotate.disposition import DISPOSITIONS, REASONS
from ss_track.schema.registry.store import load_contract_set


def test_label_enums_match_the_pack_vocabulary() -> None:
    pack = _schema("declaration/scenario-pack")["$defs"]["vocabulary"]["properties"]
    label = _schema("declaration/annotation-label")
    frame = label["$defs"]["frame"]["properties"]
    assert frame["visibility"]["enum"] == _consts(pack["visibility"])
    assert frame["camera_motion"]["enum"] == _consts(pack["camera_motion"])
    kinds = [
        branch["properties"]["kind"]["const"] for branch in label["$defs"]["geometry"]["oneOf"]
    ]
    assert kinds == _consts(pack["geometry"])
    marks = [
        item
        for item in label["$defs"]["instance"]["properties"]["non_scoring_mark"]["enum"]
        if item is not None
    ]
    assert marks == _consts(pack["non_scoring_mark"])


def test_disposition_reasons_match_the_mask_and_the_command() -> None:
    mask = _schema("declaration/annotation-mask")["$defs"]["mask-frame"]["properties"]
    command = _schema("result/command")["$defs"]["annotation-entry"]["properties"]
    assert tuple(mask["disposition"]["enum"]) == DISPOSITIONS
    assert tuple(command["disposition"]["enum"]) == DISPOSITIONS
    assert tuple(mask["reason"]["enum"]) == (*REASONS, None)
    assert tuple(command["reason"]["enum"]) == (*REASONS, None)


def _schema(name: str) -> dict[str, object]:
    contracts = load_contract_set()
    contract = contracts.named(name)
    return contracts.frozen_schema(contract, contract.versions[-1])


def _consts(node: object) -> list[object]:
    assert isinstance(node, dict)
    items = node["prefixItems"]
    assert isinstance(items, list)
    return [item["const"] for item in items]
