"""Stratified finite-population estimates for a paired selection audit."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

Z95 = 1.959963984540054


@dataclass(frozen=True, slots=True)
class AuditWindow:
    """One sampled window, its observation and the two selection decisions."""

    observation: str | None
    diverse: bool
    uniform: bool


@dataclass(frozen=True, slots=True)
class Stratum:
    """Population and sampled windows of one independent audit stratum."""

    name: str
    population: int
    sample: tuple[AuditWindow, ...]


def _variance(strata: Sequence[Stratum], coefficients: tuple[float, float, float]) -> float | None:
    total = 0.0
    for stratum in strata:
        n = len(stratum.sample)
        if n == stratum.population:
            continue
        if n < 2:
            return None
        values = []
        for item in stratum.sample:
            target = float(item.observation == "target_present")
            values.append(
                target
                * (
                    coefficients[0] * item.diverse
                    + coefficients[1] * item.uniform
                    + coefficients[2]
                )
            )
        mean = sum(values) / n
        variance = sum((value - mean) ** 2 for value in values) / (n - 1)
        total += stratum.population**2 * (1 - n / stratum.population) * variance / n
    return total


def _interval(
    value: float, variance: float | None, denominator: float, low: float
) -> list[float] | None:
    if variance is None:
        return None
    half = Z95 * math.sqrt(max(0.0, variance)) / denominator
    return [max(low, value - half), min(1.0, value + half)]


def _summarize_stratum(
    stratum: Stratum, totals: dict[str, float], selected: dict[str, float], reasons: list[str]
) -> dict[str, Any]:
    n = len(stratum.sample)
    if stratum.population < 1 or n > stratum.population:
        raise ValueError("invalid audit stratum size")
    weight = stratum.population / n if n else None
    counts = {name: 0 for name in totals}
    for item in stratum.sample:
        observation = item.observation if item.observation in counts else "unknown"
        counts[observation] += 1
        if weight is not None:
            totals[observation] += weight
            if observation == "target_present":
                selected["diverse"] += weight * item.diverse
                selected["uniform"] += weight * item.uniform
    if n == 0:
        reasons.append(f"{stratum.name}: no audit sample")
    if counts["unknown"]:
        reasons.append(f"{stratum.name}: unknown audit observations")
    return {
        "stratum_id": stratum.name,
        "population": stratum.population,
        "sample_size": n,
        "weight": weight,
        "observations": counts,
    }


def estimate(strata: Sequence[Stratum]) -> dict[str, Any]:
    """Estimate target totals and paired recall, suppressing estimates with missing observations."""
    totals = {name: 0.0 for name in ("target_present", "target_absent", "confuser", "unknown")}
    selected = {"diverse": 0.0, "uniform": 0.0}
    reasons: list[str] = []
    details = [_summarize_stratum(stratum, totals, selected, reasons) for stratum in strata]
    if not strata:
        reasons.append("empty population")
    denominator = totals["target_present"]
    if not denominator:
        reasons.append("no observed targets")
    result: dict[str, Any] = {
        "status": "inconclusive",
        "strata": details,
        "weighted_observations": totals,
        "weighted_observations_complete": bool(strata)
        and not any("unknown audit" in reason or "no audit sample" in reason for reason in reasons),
        "weighted_selected_targets": selected,
        "reasons": reasons,
        "recall": None,
        "gain": None,
    }
    if reasons:
        return result
    diverse, uniform = selected["diverse"] / denominator, selected["uniform"] / denominator
    gain = diverse - uniform
    dv = _variance(strata, (1.0, 0.0, -diverse))
    uv = _variance(strata, (0.0, 1.0, -uniform))
    gv = _variance(strata, (1.0, -1.0, -gain))
    result["recall"] = {
        "diverse": {"estimate": diverse, "interval_95": _interval(diverse, dv, denominator, 0.0)},
        "uniform": {"estimate": uniform, "interval_95": _interval(uniform, uv, denominator, 0.0)},
    }
    result["gain"] = {"estimate": gain, "interval_95": _interval(gain, gv, denominator, -1.0)}
    if gv is None:
        reasons.append(
            "uncertainty unavailable for a non-census stratum with fewer than two samples"
        )
    else:
        result["status"] = "estimated"
    return result
