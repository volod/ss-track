from ss_track.corpus.seeded import SeededDraws


def test_one_seed_gives_one_stream_of_draws() -> None:
    first = SeededDraws("blur", 7)
    second = SeededDraws("blur", 7)

    assert first.raw("radius:3", 64) == second.raw("radius:3", 64)
    assert first.integers("radius:3", 8, -5, 5) == second.integers("radius:3", 8, -5, 5)
    assert first.pick("dropped", range(50), 9) == second.pick("dropped", range(50), 9)


def test_the_stream_is_pinned_to_a_published_algorithm() -> None:
    draws = SeededDraws("blur", 7)

    assert draws.raw("radius:3", 16).hex() == "7bbd5649566a4ec403407033d1798440"
    assert draws.integers("offset:0", 4, -3, 3) == [-3, 2, 0, 2]


def test_seed_transform_and_purpose_each_give_an_independent_stream() -> None:
    base = SeededDraws("blur", 7).raw("radius:3", 32)

    assert SeededDraws("blur", 8).raw("radius:3", 32) != base
    assert SeededDraws("camera_shake", 7).raw("radius:3", 32) != base
    assert SeededDraws("blur", 7).raw("radius:4", 32) != base


def test_integers_stay_inside_the_inclusive_range_and_reach_both_ends() -> None:
    values = SeededDraws("blur", 1).integers("span", 500, -2, 2)

    assert set(values) == {-2, -1, 0, 1, 2}


def test_a_pick_is_distinct_sorted_and_comes_from_the_candidates() -> None:
    picked = SeededDraws("dropped_frames", 3).pick("dropped", range(10, 30), 6)

    assert len(set(picked)) == 6
    assert picked == sorted(picked)
    assert set(picked) <= set(range(10, 30))
