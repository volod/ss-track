"""Hand-calculated stratified estimates, paired uncertainty and incomplete evidence."""

import math

import pytest

from ss_track.corpus.evaluation.statistics import AuditWindow, Stratum, estimate


def test_weighted_recall_and_paired_delta_uncertainty() -> None:
    strata = [
        Stratum(
            "a",
            4,
            (
                AuditWindow("target_present", True, False),
                AuditWindow("target_absent", False, False),
            ),
        ),
        Stratum(
            "b",
            2,
            (AuditWindow("target_present", False, True), AuditWindow("confuser", False, False)),
        ),
    ]
    result = estimate(strata)
    assert result["status"] == "estimated"
    assert result["weighted_observations"] == {
        "target_present": 3.0,
        "target_absent": 2.0,
        "confuser": 1.0,
        "unknown": 0.0,
    }
    recall = result["recall"]
    assert isinstance(recall, dict)
    assert recall["diverse"]["estimate"] == pytest.approx(2 / 3)
    assert recall["uniform"]["estimate"] == pytest.approx(1 / 3)
    gain = result["gain"]
    assert isinstance(gain, dict)
    # Only stratum a contributes: variance of its residual total is 8/9.
    half = 1.959963984540054 * math.sqrt(8 / 9) / 3
    assert gain["interval_95"] == pytest.approx([1 / 3 - half, 1 / 3 + half])


def test_negative_gain_and_census_have_zero_width() -> None:
    result = estimate(
        [
            Stratum(
                "a",
                2,
                (
                    AuditWindow("target_present", False, True),
                    AuditWindow("target_absent", False, False),
                ),
            )
        ]
    )
    assert result["gain"] == {"estimate": -1.0, "interval_95": [-1.0, -1.0]}


@pytest.mark.parametrize(
    "strata",
    [
        [],
        [Stratum("a", 2, ())],
        [Stratum("a", 2, (AuditWindow(None, False, False),))],
        [Stratum("a", 1, (AuditWindow("unknown", False, False),))],
        [Stratum("a", 1, (AuditWindow("target_absent", False, False),))],
    ],
)
def test_missing_evidence_is_inconclusive(strata: list[Stratum]) -> None:
    result = estimate(strata)
    assert result["status"] == "inconclusive"
    assert result["recall"] is None


def test_one_non_census_sample_has_no_uncertainty() -> None:
    result = estimate([Stratum("a", 2, (AuditWindow("target_present", True, False),))])
    assert result["status"] == "inconclusive"
    assert isinstance(result["gain"], dict)
    assert result["gain"]["interval_95"] is None


def test_empty_population_does_not_report_complete_weighted_observations() -> None:
    assert estimate([])["weighted_observations_complete"] is False
