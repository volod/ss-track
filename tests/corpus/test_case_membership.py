"""A generated case is never new evidence: it stays in its parent's encounter and split."""

from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    open_frame_bundle,
    stage_corpus,
)
from ss_track.corpus.builder import CORPUS_MANIFEST_KIND
from ss_track.corpus.frames import FRAME_BUNDLE_KIND
from ss_track.corpus.sealed import read_sealed
from tests.corpus.conftest import WriteCorpus, case_of, encounter_of, group_of, stream_of

_CORPUS = "pilot-v1"
_SHAKE = {"amplitude": 2}


def _two_splits(first: ImportResult, second: ImportResult, cases: bool) -> list[dict[str, object]]:
    def recipes(*names: str) -> dict[str, object]:
        declared = [case_of(name, "camera_shake", 3, _SHAKE) for name in names]
        return {"generated_cases": declared} if cases else {}

    return [
        group_of(
            "site-a",
            "development",
            encounter_of("enc-a", stream_of(first, stream_id="cam-a", **recipes("a1", "a2"))),
        ),
        group_of(
            "site-b",
            "locked",
            encounter_of("enc-b", stream_of(second, stream_id="cam-b", **recipes("b1"))),
        ),
    ]


def test_a_case_inherits_its_parents_encounter_group_and_split(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    result = build_corpus(write_grouped_corpus(_two_splits(first, second, True)), data_root)

    manifest = read_sealed(result.manifest_path, CORPUS_MANIFEST_KIND)
    membership = {
        case["case_id"]: (case["parent_stream_id"], case["encounter_id"], case["split"])
        for case in manifest["generated_cases"]
    }
    assert membership == {
        "a1": ("cam-a", "enc-a", "development"),
        "a2": ("cam-a", "enc-a", "development"),
        "b1": ("cam-b", "enc-b", "locked"),
    }
    stage_corpus(_CORPUS, data_root)
    bundle = data_root / "corpus" / _CORPUS / "frames" / "b1" / "manifest.json"
    assert read_sealed(bundle, FRAME_BUNDLE_KIND)["generated"] == {
        "parent_stream_id": "cam-b",
        "encounter_id": "enc-b",
        "group_id": "site-b",
        "split": "locked",
    }


def test_a_case_adds_no_group_encounter_or_stream_to_any_count(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    without = build_corpus(
        write_grouped_corpus(_two_splits(first, second, False), corpus_id="plain"), data_root
    )
    withcases = build_corpus(
        write_grouped_corpus(_two_splits(first, second, True), corpus_id="cased"), data_root
    )

    assert withcases.stream_count == without.stream_count == 2
    assert withcases.generated_case_count == 3
    for split in ("development", "locked"):
        assert withcases.splits[split].group_count == without.splits[split].group_count
        assert withcases.splits[split].encounter_count == without.splits[split].encounter_count
        assert withcases.splits[split].stream_count == without.splits[split].stream_count
    assert withcases.splits["development"].generated_case_count == 2
    assert withcases.splits["locked"].generated_case_count == 1


def test_a_case_does_not_change_a_stream_record(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    plain = build_corpus(
        write_grouped_corpus(_two_splits(first, second, False), corpus_id="plain"), data_root
    )
    cased = build_corpus(
        write_grouped_corpus(_two_splits(first, second, True), corpus_id="cased"), data_root
    )

    assert (
        read_sealed(plain.manifest_path, CORPUS_MANIFEST_KIND)["streams"]
        == read_sealed(cased.manifest_path, CORPUS_MANIFEST_KIND)["streams"]
    )


def test_two_cases_cannot_share_a_name(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    cases = [
        case_of("same", "camera_shake", 1, _SHAKE),
        case_of("same", "blur", 1, {"max_radius": 1}),
    ]

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_case_cannot_take_a_stream_name_because_it_would_take_its_bundle_path(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    cases = [case_of("one", "camera_shake", 1, _SHAKE)]

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_case_named_after_a_stream_in_another_split_is_leakage(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    cases = [case_of("held-out", "camera_shake", 1, _SHAKE)]
    groups = [
        group_of(
            "site-a",
            "development",
            encounter_of("e1", stream_of(first, stream_id="dev", generated_cases=cases)),
        ),
        group_of("site-b", "locked", encounter_of("e2", stream_of(second, stream_id="held-out"))),
    ]

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_grouped_corpus(groups), data_root)

    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE


def test_a_case_keeps_its_parents_source_identity_on_every_frame(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    cases = [case_of("shaken", "camera_shake", 1, _SHAKE)]
    build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)
    stage_corpus(_CORPUS, data_root)

    bundle = open_frame_bundle(data_root / "corpus" / _CORPUS / "frames" / "shaken")

    ref = bundle.frame_ref(0)
    assert ref.stream_id == "shaken"
    assert ref.source_sha256 == imported.source_sha256
    assert ref.transform == "camera_shake"
