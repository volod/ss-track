from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode, build_corpus
from ss_track.corpus.sealed import read_sealed
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    encounter_of,
    group_of,
    import_clip,
    stream_of,
)

_CORPUS_KIND = "ss-track.corpus-manifest"


def _refused(path: Path, data_root: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(path, data_root)
    assert caught.value.code is RefusalCode.RIGHTS_CONFLICT
    assert not (data_root / "corpus").exists()
    return caught.value


def _sharing(scope: str) -> dict[str, str]:
    return {
        "holder": "Project Contributors",
        "basis": "owned",
        "retention": "project duration",
        "sharing": scope,
    }


def test_a_public_scenario_refuses_a_restricted_stream_of_a_two_stream_encounter(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    shared = import_clip(media, write_recording, data_root, 2, rights=_sharing("public"))
    closed = import_clip(media, write_recording, data_root, 4, rights=_sharing("restricted"))
    encounter = encounter_of(
        "enc01", stream_of(shared, stream_id="cam0"), stream_of(closed, stream_id="cam1")
    )
    groups = [group_of("site-a", "development", encounter)]
    scenario = {"sharing": "public", "max_sensitivity": "high"}

    refusal = _refused(write_grouped_corpus(groups, scenario_rights=scenario), data_root)

    assert refusal.details == {
        "conflicts": [
            {
                "stream_id": "cam1",
                "source_sha256": closed.source_sha256,
                "field": "sharing",
                "source_value": "restricted",
                "scenario_value": "public",
            }
        ]
    }


@pytest.mark.parametrize(
    ("level", "limit", "accepted"),
    [
        ("low", "low", True),
        ("moderate", "low", False),
        ("moderate", "moderate", True),
        ("high", "moderate", False),
        ("high", "high", True),
    ],
)
def test_a_source_more_sensitive_than_the_scenario_allows_is_refused(
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    level: str,
    limit: str,
    accepted: bool,
) -> None:
    source = import_clip(media, write_recording, data_root, 2, sensitivity={"level": level})
    declared = write_corpus(
        [stream_of(source)], scenario_rights={"sharing": "restricted", "max_sensitivity": limit}
    )

    if accepted:
        assert build_corpus(declared, data_root).status == "built"
        return
    conflicts = _refused(declared, data_root).details["conflicts"]
    assert isinstance(conflicts, list) and isinstance(conflicts[0], dict)
    assert conflicts[0]["field"] == "sensitivity"


def test_every_conflict_is_named_at_once(
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    source = import_clip(media, write_recording, data_root, 2, sensitivity={"level": "high"})
    other = import_clip(media, write_recording, data_root, 4, sensitivity={"level": "high"})
    streams = [stream_of(source, stream_id="a"), stream_of(other, stream_id="b")]
    scenario = {"sharing": "public", "max_sensitivity": "low"}

    refusal = _refused(write_corpus(streams, scenario_rights=scenario), data_root)

    conflicts = refusal.details["conflicts"]
    assert isinstance(conflicts, list)
    assert [(item["stream_id"], item["field"]) for item in conflicts] == [  # type: ignore[call-overload,index,misc]
        ("a", "sharing"),
        ("a", "sensitivity"),
        ("b", "sharing"),
        ("b", "sensitivity"),
    ]


def test_a_narrower_scenario_keeps_a_public_source_as_a_recorded_fact(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    source = import_clip(media, write_recording, data_root, 2, rights=_sharing("public"))

    result = build_corpus(write_corpus([stream_of(source)]), data_root)

    manifest = read_sealed(result.manifest_path, _CORPUS_KIND)
    streams = manifest["streams"]
    assert isinstance(streams, list) and isinstance(streams[0], dict)
    assert streams[0]["rights"] == _sharing("public")
    assert manifest["scenario_rights"] == {"sharing": "restricted", "max_sensitivity": "high"}
