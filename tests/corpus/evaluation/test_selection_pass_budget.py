"""Hand-counted selection passes: the pilot's 85-versus-87 workload, matched by recorded work.

The pool has 500 windows in one stratum and the shared audit samples w000-w231. Diverse selects
w000-w014 (15 in the audit) and w232-w316 (85 outside); uniform selects w015-w027 (13 in the
audit) and w317-w403 (87 outside). Beyond the audit both reviews pay 85 and 87 windows, so equal
selections of 100 are unequal work. A selection pass of each run reviews its 100 selected windows,
so the work is 100 and 100 whatever the overlap, and the windows reviewers look at in all are
232 + 100 + 100 = 432. Audit targets are w000-w004, w015-w017 and w100-w104.
"""

from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.evaluation.workload import (
    REASON_PASS_INCOMPLETE,
    REASON_PASS_UNPAIRED,
    REASON_SELECTED,
    REASON_WORKLOAD,
)
from ss_track.corpus.review.selection_pass import SelectionPass
from tests.corpus.evaluation._budget import STREAM, Window, _budget, _evaluate, _run

AUDIT = "audit-1"
_TARGETS = {*range(5), *range(15, 18), *range(100, 105)}


def _name(index: int) -> str:
    return f"w{index:03d}"


def _windows(uniform_outside: int = 87) -> tuple[Window, ...]:
    windows: list[Window] = []
    for index in range(500):
        sampled = index < 232
        observed = "target_present" if index in _TARGETS else "target_absent"
        windows.append(
            Window(
                _name(index),
                sampled=sampled,
                diverse_selected=index < 15 or 232 <= index < 317,
                uniform_selected=15 <= index < 28 or 317 <= index < 317 + uniform_outside,
                observation=observed if sampled else None,
            )
        )
    return tuple(windows)


_PILOT = _windows()
_DIVERSE = [*range(15), *range(232, 317)]
_UNIFORM = [*range(15, 28), *range(317, 404)]


def _pass(indexes: list[int], seen: dict[int, str] | None = None) -> SelectionPass:
    """Agree with every audit observation, except where `seen` states another."""
    found = seen or {}
    return SelectionPass(
        "pass reviewer",
        {(STREAM, _name(index)): found.get(index, _agreeing(index)) for index in indexes},
    )


def _agreeing(index: int) -> str:
    return "target_present" if index in _TARGETS else "target_absent"


def _passes(**options: Any) -> dict[str, Any]:
    return _evaluate(
        options.pop("windows", _PILOT),
        diverse_audit=AUDIT,
        uniform_audit=AUDIT,
        diverse_pass=options.pop("diverse_pass", _pass(_DIVERSE)),
        uniform_pass=options.pop("uniform_pass", _pass(_UNIFORM)),
        **options,
    )


def test_the_pilot_shared_audit_pays_85_and_87_and_is_unmatched() -> None:
    result = _evaluate(_PILOT, diverse_audit=AUDIT, uniform_audit=AUDIT)
    budget = _budget(result)
    assert _run(result, "diverse")["selected"] == _run(result, "uniform")["selected"] == 100
    assert _run(result, "diverse")["audit_selected_overlap"] == 15
    assert _run(result, "uniform")["audit_selected_overlap"] == 13
    assert budget["protocol"] == "shared_audit"
    assert budget["shared_audit_windows"] == 232
    assert budget["per_method_windows"] == {"diverse": 317, "uniform": 319}
    assert budget["additions"] == {"diverse": 85, "uniform": 87}
    assert budget["status"] == "unmatched"
    assert budget["reasons"] == [REASON_WORKLOAD]
    assert "selection_pass" not in budget  # a review without a pass reports as before
    assert result["status"] == "inconclusive"


def test_complete_passes_match_the_pilot_workload_without_changing_the_estimate() -> None:
    shared = _evaluate(_PILOT, diverse_audit=AUDIT, uniform_audit=AUDIT)
    result = _passes()
    budget = _budget(result)
    passes = budget["selection_pass"]
    assert budget["protocol"] == "selection_pass"
    assert budget["status"] == "matched"
    assert budget["reasons"] == []
    assert budget["comparable_windows"] == {"diverse": 100, "uniform": 100}
    assert budget["additions"] == {"diverse": 85, "uniform": 87}  # still shown
    assert passes["review_exposures"] == 432
    assert result["unique_offered_windows"] == 404
    for side, repeats in (("diverse", 15), ("uniform", 13)):
        account = passes[side]
        assert account["expected_windows"] == account["reviewed_windows"] == 100
        assert account["missing_windows"] == 0
        assert account["audit_repeats"] == repeats
        assert "reviewer_minutes" not in account  # unrecorded, not zero
    assert result["status"] == "estimated"
    assert result["audit"]["recall"] == shared["audit"]["recall"]
    assert result["audit"]["gain"] == shared["audit"]["gain"]
    assert result["audit"]["strata"] == shared["audit"]["strata"]


def test_pass_findings_and_disagreements_are_shown_and_never_reach_the_estimate() -> None:
    plain = _passes()
    # Diverse's pass sees a target in w232, outside the audit, and in w010, which the audit
    # observed as absent; uniform's pass calls the audit target w015 absent and w016 unknown.
    result = _passes(
        diverse_pass=_pass(_DIVERSE, {232: "target_present", 10: "target_present"}),
        uniform_pass=_pass(_UNIFORM, {15: "target_absent", 16: "unknown"}),
    )
    passes = _budget(result)["selection_pass"]
    assert passes["diverse"]["observations"] == {  # w000-w004 agree with the audit
        "confuser": 0,
        "target_absent": 93,
        "target_present": 7,
        "unknown": 0,
    }
    assert passes["diverse"]["targets_outside_audit"] == 1
    assert passes["uniform"]["observations"]["unknown"] == 1
    assert passes["uniform"]["targets_outside_audit"] == 0
    rows = [(row["run"], row["candidate_id"]) for row in passes["disagreements"]]
    assert rows == [("diverse", "w010"), ("uniform", "w015")]  # w016 is unknown
    first = passes["disagreements"][0]
    assert first["review_observation"] == "target_absent"
    assert first["pass_observation"] == "target_present"
    assert first["audit_sampled"] is True
    assert result["audit"] == plain["audit"]
    assert result["observations"] == plain["observations"]


def test_an_incomplete_pass_is_unmeasured_work() -> None:
    result = _passes(diverse_pass=_pass(_DIVERSE[:-1]))
    budget = _budget(result)
    assert budget["status"] == "unmeasured"
    assert budget["reasons"] == [REASON_PASS_INCOMPLETE]
    assert budget["selection_pass"]["diverse"]["missing_windows"] == 1
    assert budget["selection_pass"]["review_exposures"] == 431
    assert result["status"] == "inconclusive"


@pytest.mark.parametrize("side", ["diverse", "uniform"])
def test_a_pass_in_one_review_only_is_unrecorded(side: str) -> None:
    result = _passes(**{f"{side}_pass": None})
    budget = _budget(result)
    assert budget["protocol"] == "unrecorded"
    assert budget["status"] == "unmeasured"
    assert budget["reasons"] == [REASON_PASS_UNPAIRED]
    assert budget["selection_pass"][side] is None
    assert budget["selection_pass"]["review_exposures"] is None
    assert result["status"] == "inconclusive"


def test_passes_without_one_shared_audit_are_unrecorded() -> None:
    result = _evaluate(_PILOT, diverse_pass=_pass(_DIVERSE), uniform_pass=_pass(_UNIFORM))
    budget = _budget(result)
    assert budget["protocol"] == "unrecorded"
    assert budget["reasons"] == [REASON_PASS_UNPAIRED]
    assert budget["selection_pass"]["review_exposures"] is None


def test_unequal_selections_stay_unmatched_with_complete_passes() -> None:
    windows = _windows(uniform_outside=85)
    result = _passes(windows=windows, uniform_pass=_pass(_UNIFORM[:-2]))
    budget = _budget(result)
    assert _run(result, "uniform")["selected"] == 98
    assert budget["selection_pass"]["uniform"]["missing_windows"] == 0
    assert budget["comparable_windows"] == {"diverse": 100, "uniform": 98}
    assert budget["status"] == "unmatched"
    assert budget["reasons"] == [REASON_SELECTED, REASON_WORKLOAD]


def test_a_withheld_selection_is_not_expected_and_cannot_be_in_a_pass() -> None:
    held = frozenset({(STREAM, _name(232))})
    result = _passes(diverse_withheld=held, diverse_pass=_pass(_DIVERSE[:15] + _DIVERSE[16:]))
    budget = _budget(result)
    assert budget["selection_pass"]["diverse"]["expected_windows"] == 99
    assert budget["selection_pass"]["diverse"]["missing_windows"] == 0
    assert budget["comparable_windows"] == {"diverse": 99, "uniform": 100}
    assert budget["status"] == "unmatched"
    assert budget["reasons"] == [REASON_WORKLOAD]

    with pytest.raises(CorpusRefusal) as caught:
        _passes(diverse_withheld=held)
    details: Any = caught.value.details
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert details["locked_without_policy"] == [{"stream_id": STREAM, "candidate_id": "w232"}]


def test_a_pass_replayed_onto_the_other_run_is_refused() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        _passes(diverse_pass=_pass(_UNIFORM))
    details: Any = caught.value.details
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert details["run_id"] == "diverse"
    assert len(details["not_selected"]) == 100
