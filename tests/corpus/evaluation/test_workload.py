"""Hand-calculated review workloads, including a false match on equal selection counts."""

import pytest

from ss_track.corpus.evaluation.workload import (
    REASON_MISSING,
    REASON_PROTOCOL,
    REASON_SELECTED,
    REASON_WORKLOAD,
)
from tests.corpus.evaluation._budget import STREAM, Window, _budget, _evaluate, _gain, _run

# Census of two audit windows. Each method selects one, so the overlap is one and the
# offered set is the audit set: 2 and 2. Uniform selects the only target, so the gain is -1.
_MATCHED = (
    Window("a", sampled=True, uniform_selected=True, observation="target_present"),
    Window("b", sampled=True, diverse_selected=True, observation="target_absent"),
)
# Both methods select two windows. Diverse selects the audit draw; uniform selects outside it.
# Offered is 2 versus 2 + 2 = 4.
_OVERLAP = (
    Window("a", sampled=True, diverse_selected=True, observation="target_present"),
    Window("b", sampled=True, diverse_selected=True, observation="target_present"),
    Window("c", uniform_selected=True, observation="target_absent"),
    Window("d", uniform_selected=True, observation="target_absent"),
)


def test_equal_selection_counts_with_different_overlap_are_inconclusive() -> None:
    result = _evaluate(_OVERLAP)
    budget = _budget(result)
    assert _run(result, "diverse")["selected"] == _run(result, "uniform")["selected"] == 2
    assert _run(result, "diverse")["offered_windows"] == 2
    assert _run(result, "uniform")["offered_windows"] == 4
    assert _run(result, "diverse")["audit_selected_overlap"] == 2
    assert _run(result, "uniform")["audit_selected_overlap"] == 0
    assert _run(result, "diverse")["sibling_offers"] == 0
    assert result["unique_offered_windows"] == 4
    assert budget["protocol"] == "per_run"
    assert budget["status"] == "unmatched"
    assert budget["shared_audit_windows"] == 2
    assert budget["per_method_windows"] == {"diverse": 2, "uniform": 4}
    assert budget["additions"] == {"diverse": 0, "uniform": 2}
    assert budget["comparable_windows"] == {"diverse": 2, "uniform": 4}
    assert budget["reasons"] == [REASON_WORKLOAD]
    assert result["status"] == "inconclusive"
    assert result["audit"]["reasons"] == [REASON_WORKLOAD]
    assert _gain(result) == pytest.approx(1.0)


def test_matched_budget_keeps_a_negative_gain() -> None:
    result = _evaluate(_MATCHED)
    budget = _budget(result)
    gain = result["audit"]["gain"]
    assert isinstance(gain, dict)
    assert result["status"] == "estimated"
    assert gain == {"estimate": -1.0, "interval_95": [-1.0, -1.0]}
    assert _run(result, "diverse")["offered_windows"] == 2
    assert _run(result, "uniform")["offered_windows"] == 2
    assert _run(result, "diverse")["audit_selected_overlap"] == 1
    assert _run(result, "uniform")["audit_selected_overlap"] == 1
    assert budget["status"] == "matched"
    assert budget["reasons"] == []
    assert budget["shared_audit_windows"] == 2
    assert budget["per_method_windows"] == {"diverse": 2, "uniform": 2}
    assert budget["additions"] == {"diverse": 0, "uniform": 0}
    assert result["unique_offered_windows"] == 2


def test_shared_audit_compares_additions_and_counts_the_sample_once() -> None:
    matched = _evaluate(_MATCHED, diverse_audit="audit-1", uniform_audit="audit-1")
    budget = _budget(matched)
    assert matched["status"] == "estimated"
    assert _gain(matched) == pytest.approx(-1.0)
    assert budget["protocol"] == "shared_audit"
    assert budget["status"] == "matched"
    assert budget["comparable_windows"] == {"diverse": 0, "uniform": 0}
    assert budget["shared_audit_windows"] == 2

    overlap = _evaluate(_OVERLAP, diverse_audit="audit-1", uniform_audit="audit-1")
    overlap_budget = _budget(overlap)
    assert overlap["status"] == "inconclusive"
    assert overlap_budget["protocol"] == "shared_audit"
    assert overlap_budget["status"] == "unmatched"
    assert overlap_budget["comparable_windows"] == {"diverse": 0, "uniform": 2}
    assert overlap_budget["per_method_windows"] == {"diverse": 2, "uniform": 4}


def test_sibling_offer_is_one_extra_window() -> None:
    sibling = Window("s", sibling=True, on=("diverse", "uniform"), slot=3)
    both = _evaluate((*_MATCHED, sibling))
    assert both["status"] == "estimated"
    assert _gain(both) == pytest.approx(-1.0)
    assert _run(both, "diverse")["sibling_offers"] == 1
    assert _run(both, "uniform")["sibling_offers"] == 1
    assert _run(both, "diverse")["offered_windows"] == 3
    assert _budget(both)["additions"] == {"diverse": 1, "uniform": 1}
    assert both["unique_offered_windows"] == 3

    diverse_only = Window("s", sibling=True, on=("diverse",), slot=3)
    one = _evaluate((*_MATCHED, diverse_only))
    assert _run(one, "diverse")["offered_windows"] == 3
    assert _run(one, "diverse")["sibling_offers"] == 1
    assert _run(one, "uniform")["offered_windows"] == 2
    assert _run(one, "uniform")["sibling_offers"] == 0
    assert one["unique_offered_windows"] == 3
    assert _budget(one)["status"] == "unmatched"
    assert _budget(one)["reasons"] == [REASON_WORKLOAD]
    assert one["status"] == "inconclusive"


def test_withheld_sibling_is_counted_and_not_offered() -> None:
    sibling = Window("s", sibling=True, slot=4)
    held = frozenset({(STREAM, "s")})
    both = _evaluate((*_MATCHED, sibling), diverse_withheld=held, uniform_withheld=held)
    assert both["status"] == "estimated"
    assert _gain(both) == pytest.approx(-1.0)
    assert _run(both, "diverse")["withheld_windows"] == 1
    assert _run(both, "uniform")["withheld_windows"] == 1
    assert _run(both, "diverse")["sibling_offers"] == 0
    assert _run(both, "diverse")["offered_windows"] == 2
    assert _budget(both)["status"] == "matched"
    assert both["unique_offered_windows"] == 2

    one = _evaluate((*_MATCHED, sibling), diverse_withheld=held)
    assert _run(one, "diverse")["withheld_windows"] == 1
    assert _run(one, "diverse")["sibling_offers"] == 0
    assert _run(one, "diverse")["offered_windows"] == 2
    assert _run(one, "uniform")["withheld_windows"] == 0
    assert _run(one, "uniform")["sibling_offers"] == 1
    assert _run(one, "uniform")["offered_windows"] == 3
    assert _budget(one)["status"] == "unmatched"
    assert one["status"] == "inconclusive"


def test_unrecorded_protocol_keeps_counts_and_is_unmeasured() -> None:
    result = _evaluate(_MATCHED, diverse_audit="audit-1")
    budget = _budget(result)
    assert budget["protocol"] == "unrecorded"
    assert budget["status"] == "unmeasured"
    assert budget["reasons"] == [REASON_PROTOCOL]
    assert budget["per_method_windows"] == {"diverse": 2, "uniform": 2}
    assert result["status"] == "inconclusive"
    assert result["audit"]["reasons"] == [REASON_PROTOCOL]
    assert _gain(result) == pytest.approx(-1.0)


def test_missing_withheld_window_is_unmeasured() -> None:
    result = _evaluate(_MATCHED, diverse_withheld=frozenset({(STREAM, "missing")}))
    budget = _budget(result)
    assert _run(result, "diverse")["withheld_windows"] == 1
    assert _run(result, "diverse")["offered_windows"] == 2
    assert budget["status"] == "unmeasured"
    assert budget["reasons"] == [REASON_MISSING]
    assert result["status"] == "inconclusive"
    assert REASON_WORKLOAD not in budget["reasons"]


def test_equal_offered_counts_still_reject_unequal_selection() -> None:
    windows = (
        Window(
            "a",
            sampled=True,
            diverse_selected=True,
            uniform_selected=True,
            observation="target_present",
        ),
        Window("b", sampled=True, diverse_selected=True, observation="target_present"),
    )
    result = _evaluate(windows)
    assert _run(result, "diverse")["selected"] == 2
    assert _run(result, "uniform")["selected"] == 1
    assert _run(result, "diverse")["offered_windows"] == 2
    assert _run(result, "uniform")["offered_windows"] == 2
    assert _budget(result)["status"] == "unmatched"
    assert _budget(result)["reasons"] == [REASON_SELECTED]
    assert result["status"] == "inconclusive"


def test_recorded_minutes_are_explicit_and_missing_minutes_are_not_zero() -> None:
    unequal = _evaluate(_MATCHED, diverse_minutes=12, uniform_minutes=15)
    assert unequal["status"] == "estimated"
    assert unequal["review_effort_minutes"] == [12, 15]
    assert _budget(unequal)["recorded_effort"] == "unequal"
    assert _budget(unequal)["status"] == "matched"

    missing = _evaluate(_MATCHED, diverse_minutes=None, uniform_minutes=None)
    assert missing["status"] == "estimated"
    assert missing["review_effort_minutes"] == [None, None]
    assert _budget(missing)["recorded_effort"] == "unmeasured"
    assert _budget(missing)["status"] == "matched"
