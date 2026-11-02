"""Where the local validator is stricter than the standard, and how it reports."""

from pathlib import Path

import pytest
from referencing import Registry

from ss_track.schema.strict import VIOLATION_LIMIT, violations
from tests.schema.conftest import STANDARD


def _schema(**fields: object) -> dict[str, object]:
    return {"$schema": STANDARD} | fields


def _found(document: object, **fields: object) -> list[str]:
    return [item.keyword for item in violations(document, _schema(**fields), Registry())]


@pytest.mark.parametrize("value", [1.0, True, "1", None])
def test_only_a_true_integer_is_an_integer(value: object) -> None:
    assert _found(value, type="integer") == ["type"]


def test_an_integer_is_still_an_integer() -> None:
    assert _found(3, type="integer") == []


def test_a_const_integer_with_a_type_refuses_its_float_twin() -> None:
    assert _found(1.0, type="integer", const=1) == ["type"]


def test_a_value_ending_in_a_newline_does_not_match_an_anchored_pattern() -> None:
    assert _found("abc\n", type="string", pattern="^[a-c]+$") == ["pattern"]
    assert _found("abc", type="string", pattern="^[a-c]+$") == []


def test_a_pattern_with_no_end_anchor_still_searches() -> None:
    assert _found("abc\n", type="string", pattern="^[a-c]+") == []


def test_a_pattern_ignores_what_is_not_a_string() -> None:
    assert _found(None, type=["string", "null"], pattern="^a$") == []


@pytest.mark.parametrize("value", ["2026-02-30", "20260101", "2026-W01-1", "not a date"])
def test_a_date_is_a_real_calendar_date_in_one_form(value: str) -> None:
    assert _found(value, type="string", format="date") == ["format"]


def test_a_valid_date_passes() -> None:
    assert _found("2026-02-28", type="string", format="date") == []


def test_a_violation_is_named_by_json_pointer() -> None:
    schema = _schema(
        type="object",
        properties={
            "a/b": {
                "type": "array",
                "items": {"type": "object", "properties": {"c~": {"type": "integer"}}},
            }
        },
    )

    found = violations({"a/b": [{"c~": "x"}]}, schema, Registry())

    assert [item.pointer for item in found] == ["/a~1b/0/c~0"]
    assert found[0].to_record()["keyword"] == "type"


def test_a_report_is_capped_and_ordered(tmp_path: Path) -> None:
    names = {f"key{index:03}": {"type": "integer"} for index in range(VIOLATION_LIMIT * 2)}
    document = dict.fromkeys(names, "x")

    first = violations(document, _schema(type="object", properties=names), Registry())
    second = violations(document, _schema(type="object", properties=names), Registry())

    assert len(first) == VIOLATION_LIMIT
    assert first == second
    assert [item.pointer for item in first] == sorted(item.pointer for item in first)
