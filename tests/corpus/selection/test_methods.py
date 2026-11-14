"""Selection methods rank pool windows within a budget and state every probability they used."""

from collections.abc import Sequence

import numpy as np

from ss_track.corpus.selection.methods import SelectionSpec, Window, select

UNIFORM = SelectionSpec("uniform", 3, 11, (), ())
DIVERSE = SelectionSpec("ssl-diverse", 2, None, ("deviation", "motion"), ("clip",))


def _window(
    name: str,
    values: dict[str, float] | None = None,
    angle: float = 0.0,
    *,
    stream: str = "one",
    pool: bool = True,
    locked: bool = False,
) -> Window:
    descriptor = {"clip": np.array([np.cos(angle), np.sin(angle)])}
    return Window(stream, name, pool, locked, values or {}, descriptor)


def _pool(count: int, stream: str = "one", locked: bool = False) -> list[Window]:
    return [_window(f"pool-{i:03d}", stream=stream, locked=locked) for i in range(count)]


def _selected(decided: dict[tuple[str, str], dict[str, object]]) -> list[tuple[str, str]]:
    ranked = [(item["rank"], key) for key, item in decided.items() if item["status"] == "selected"]
    return [key for _, key in sorted(ranked)]  # type: ignore[type-var]


def test_uniform_draws_its_budget_with_one_known_probability_and_repeats_by_seed() -> None:
    windows: Sequence[Window] = [*_pool(8), _window("sibling-x-00000001", pool=False)]

    decided = select(UNIFORM, windows)

    assert len(_selected(decided)) == 3
    pool = [decided[("one", f"pool-{i:03d}")] for i in range(8)]
    assert {item["probability"] for item in pool} == {3 / 8}
    assert decided[("one", "sibling-x-00000001")] == {"status": "not_selected", "probability": 0.0}
    assert select(UNIFORM, list(reversed(windows))) == decided
    other_seed = SelectionSpec("uniform", 3, 12, (), ())
    assert _selected(select(other_seed, windows)) != _selected(decided)


def test_a_locked_stream_is_excluded_but_counts_against_nothing() -> None:
    windows = [*_pool(4), *_pool(4, stream="held", locked=True)]

    decided = select(UNIFORM, windows)

    held = [decided[("held", f"pool-{i:03d}")] for i in range(4)]
    assert held == [{"status": "excluded", "reason": "operator_excluded"}] * 4
    assert {decided[("one", f"pool-{i:03d}")]["probability"] for i in range(4)} == {3 / 4}


def test_a_budget_above_the_eligible_pool_selects_it_all_with_probability_one() -> None:
    decided = select(SelectionSpec("uniform", 9, 1, (), ()), _pool(2))

    assert [item["probability"] for item in decided.values()] == [1.0, 1.0]


def test_diverse_ranks_by_mean_percentile_and_skips_a_near_copy_of_a_pick() -> None:
    windows = [
        _window("pool-000", {"deviation": 0.9, "motion": 5.0}, angle=0.0),
        _window("pool-001", {"deviation": 0.8, "motion": 5.0}, angle=0.01),  # a copy of 000
        _window("pool-002", {"deviation": 0.1, "motion": 1.0}, angle=1.4),
        _window("pool-003", {"deviation": 0.5, "motion": 2.0}, angle=1.5),
        _window("pool-004", {"motion": 9.0}),  # deviation unavailable
    ]

    decided = select(DIVERSE, windows)

    # Percentiles over four windows: deviation 1, 2/3, 0, 1/3; motion 5/6, 5/6 (a tie), 0, 1/3.
    # Priorities: 11/12, 3/4, 0, 1/3. After 000 is picked, each window loses half its cosine to
    # it: 001 keeps 0.75 - 0.5 cos 0.01 = 0.25, and 003 keeps 1/3 - 0.5 cos 1.5 = 0.298.
    assert _selected(decided) == [("one", "pool-000"), ("one", "pool-003")]
    assert decided[("one", "pool-001")] == {"status": "not_selected", "probability": 0.0}
    assert decided[("one", "pool-004")] == {"status": "excluded", "reason": "features_unavailable"}


def test_unranked_selects_nothing_and_excludes_nothing() -> None:
    windows = [*_pool(2), *_pool(1, stream="held", locked=True)]

    decided = select(SelectionSpec("unranked", 0, None, (), ()), windows)

    assert set(map(str, (item["status"] for item in decided.values()))) == {"not_selected"}
