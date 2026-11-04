"""The oracle fails closed: what it cannot decide or confirm is an error, never a verdict."""

import json
from typing import Any

import pytest

from tests.schema.compatibility import _oracle
from tests.schema.compatibility._oracle import Undecided, require_oracle_agreement, verdict
from tests.schema.compatibility.test_evolution import NUMBER, TEXT, obj

OPEN = obj({}) | {"additionalProperties": True}
CONSTRAINED = obj({"value": TEXT}) | {"additionalProperties": True}


def test_an_undecided_pattern_names_the_unsupported_relationship() -> None:
    with pytest.raises(Undecided, match=r"\^\.\+\$ to \^\[ab\]\+\$: character '\.'"):
        verdict(TEXT | {"pattern": "^.+$"}, TEXT | {"pattern": "^[ab]+$"})


def test_an_unknown_verdict_without_a_witness_is_undecided(monkeypatch: pytest.MonkeyPatch) -> None:
    def unknown(*_: Any) -> dict[str, str]:
        return {"status": "unknown", "reason": "no witness found"}

    monkeypatch.setattr(_oracle.jsoncompat, "analyze_compat", unknown)
    with pytest.raises(Undecided, match="no witness found"):
        verdict(OPEN, OPEN)
    assert verdict(OPEN, CONSTRAINED).witness == {"value": 0}


def test_a_counterexample_the_strict_validator_does_not_confirm_is_undecided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def wrong(*_: Any) -> dict[str, Any]:
        return {
            "status": "incompatible",
            "counterexample": {"value": "a"},
            "counterexample_json": "x",
        }

    monkeypatch.setattr(_oracle.jsoncompat, "analyze_compat", wrong)
    with pytest.raises(Undecided, match="counterexample not confirmed"):
        verdict(OPEN, CONSTRAINED)


def test_a_classifier_that_misses_a_break_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_oracle, "required_bump", lambda _: "minor")
    with pytest.raises(
        AssertionError, match=r"backward=True, oracle=False, witness=\{\"value\": 0\}"
    ):
        require_oracle_agreement(OPEN, CONSTRAINED)


def test_a_closed_object_is_not_opened_by_the_rewrite() -> None:
    assert verdict(obj({}), obj({"value": TEXT})).compatible
    assert verdict(obj({"value": TEXT}), obj({})).witness == {"value": ""}


def test_a_bound_jsoncompat_leaves_unknown_is_refuted_by_its_edge() -> None:
    assert verdict(NUMBER | {"minimum": 1}, NUMBER | {"minimum": 2}).witness == 1
    assert verdict(NUMBER | {"maximum": 3}, NUMBER | {"maximum": 2}).witness == 3


def test_the_search_alone_catches_the_open_object_jsoncompat_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_oracle, "_declare_open", lambda *_: None)
    assert verdict(OPEN, CONSTRAINED).witness == {"value": 0}


def test_open_object_workaround_is_still_needed() -> None:
    """Fail once the pinned jsoncompat sees the open-object break itself.

    jsoncompat 0.5.0 calls an optional constraint added inside an open object compatible, and
    `_oracle._declare_open` works around it. When this test fails, the pinned release fixed the
    defect: remove `_declare_open` and this test, and keep the oracle's other agreement tests.
    """
    for old, new in ((OPEN, CONSTRAINED), (obj({"details": OPEN}), obj({"details": CONSTRAINED}))):
        raw = _oracle.jsoncompat.analyze_compat(json.dumps(old), json.dumps(new), "deserializer")
        assert raw == {"status": "compatible"}, (
            f"jsoncompat now returns {raw}: remove the `_declare_open` workaround"
        )
        assert verdict(old, new).witness is not None
