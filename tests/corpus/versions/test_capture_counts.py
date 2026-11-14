"""Build results count encounters by capture judgment and leave the manifest unchanged."""

import json
from pathlib import Path

from ss_track.core.evidence.sealed import read_sealed
from ss_track.corpus import ImportResult, RefusalCode, amend_source_terms, build_corpus
from ss_track.corpus.records.kinds import CORPUS_MANIFEST, SOURCE_MANIFEST
from ss_track.corpus.versions.capture_counts import CAMERA_CONTROL_MODES, OBSERVER_PLATFORMS
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.enforce import older_remedy
from tests.corpus.conftest import (
    HEAD,
    TAIL,
    WriteCorpus,
    WriteRecording,
    case_of,
    encounter_of,
    group_of,
    import_clip,
    reseal,
    stream_of,
)
from tests.corpus.versions._grouping import refused_grouping

_HAND = {
    "camera_control_mode": {
        "operator_steered": 1,
        "fixed_camera": 2,
        "autonomous_camera": 1,
        "unknown": 1,
    },
    "observer_platform": {
        "ground_fixed": 1,
        "ground_handheld": 2,
        "airborne": 1,
        "unknown": 1,
    },
}
_SHAKE = {"amplitude": 2}


def test_count_bins_follow_the_closed_capture_vocabulary() -> None:
    contracts = load_contract_set()
    source = contracts.named("record/source-manifest")
    source_schema = contracts.frozen_schema(source, source.versions[-1])
    capture = source_schema["properties"]["capture"]["properties"]
    command = contracts.named("result/command")
    command_schema = contracts.frozen_schema(command, command.versions[-1])
    counts = command_schema["properties"]["capture_encounters"]["properties"]

    assert tuple(capture["camera_control_mode"]["enum"]) == CAMERA_CONTROL_MODES
    assert tuple(capture["observer_platform"]["enum"]) == OBSERVER_PLATFORMS
    assert tuple(counts["camera_control_mode"]["required"]) == CAMERA_CONTROL_MODES
    assert tuple(counts["observer_platform"]["required"]) == OBSERVER_PLATFORMS


def test_a_build_counts_each_encounter_once_in_every_bin_it_uses(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    omitted = _import(media, write_recording, data_root, 20, None)
    repeated = _import(
        media,
        write_recording,
        data_root,
        22,
        {"camera_control_mode": "fixed_camera", "observer_platform": "ground_handheld"},
    )
    another = _import(
        media,
        write_recording,
        data_root,
        24,
        {"camera_control_mode": "fixed_camera", "observer_platform": "ground_handheld"},
    )
    steered = _import(
        media,
        write_recording,
        data_root,
        26,
        {"camera_control_mode": "operator_steered", "observer_platform": "ground_fixed"},
    )
    airborne = _import(
        media,
        write_recording,
        data_root,
        28,
        {"camera_control_mode": "autonomous_camera", "observer_platform": "airborne"},
    )
    members = (omitted, repeated, another, steered, airborne)

    plain = build_corpus(
        write_grouped_corpus(_groups(members, case=False), corpus_id="plain"), data_root
    )
    cased_path = write_grouped_corpus(_groups(members, case=True), corpus_id="cased")
    cased = build_corpus(cased_path, data_root)
    again = build_corpus(cased_path, data_root)

    assert plain.capture_encounters.to_record() == _HAND
    assert cased.capture_encounters.to_record() == _HAND
    assert cased.generated_case_count == 1
    assert plain.generated_case_count == 0
    assert sum(cased.capture_encounters.camera_control_mode.values()) == 5
    assert cased.splits["development"].encounter_count == 4
    assert (again.status, again.manifest_sha256) == ("unchanged", cased.manifest_sha256)
    assert again.capture_encounters.to_record() == _HAND
    manifest = read_sealed(cased.manifest_path, CORPUS_MANIFEST)
    sealed = json.dumps(manifest)
    assert "capture_encounters" not in manifest
    assert "camera_control_mode" not in sealed
    assert "observer_platform" not in sealed


def test_unused_capture_bins_are_zero(
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    imported = _import(
        media,
        write_recording,
        data_root,
        32,
        {"camera_control_mode": "operator_steered", "observer_platform": "airborne"},
    )

    result = build_corpus(write_corpus([stream_of(imported)]), data_root)

    counts = result.capture_encounters.to_record()
    assert counts == {
        "camera_control_mode": {
            "operator_steered": 1,
            "fixed_camera": 0,
            "autonomous_camera": 0,
            "unknown": 0,
        },
        "observer_platform": {
            "ground_fixed": 0,
            "ground_handheld": 0,
            "airborne": 1,
            "unknown": 0,
        },
    }


def test_a_historical_source_refuses_then_counts_after_amendment(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    imported = import_clip(media, write_recording, data_root, 34)
    historical = _historical_capture(imported.manifest_path)
    groups = [
        group_of("site", "development", encounter_of("enc", stream_of(imported, stream_id="one")))
    ]

    refusal = refused_grouping(
        write_grouped_corpus, groups, data_root, RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    )
    assert refusal.details["disposition"] == "facts"
    assert refusal.details["remedy"] == older_remedy(SOURCE_MANIFEST.kind, 2)

    declaration = write_recording(
        "clip-34.mkv",
        capture={"camera_control_mode": "operator_steered", "observer_platform": "airborne"},
    )
    amended = amend_source_terms(declaration, data_root, amend_capture=True, amend_terms=False)
    assert amended.replaced_path is not None
    assert amended.replaced_path.read_bytes() == historical
    built = build_corpus(write_grouped_corpus(groups), data_root)
    again = build_corpus(write_grouped_corpus(groups), data_root)

    assert built.capture_encounters.to_record() == {
        "camera_control_mode": {
            "operator_steered": 1,
            "fixed_camera": 0,
            "autonomous_camera": 0,
            "unknown": 0,
        },
        "observer_platform": {
            "ground_fixed": 0,
            "ground_handheld": 0,
            "airborne": 1,
            "unknown": 0,
        },
    }
    assert again.status == "unchanged"
    assert again.manifest_sha256 == built.manifest_sha256


def _import(
    media: Path,
    write_recording: WriteRecording,
    data_root: Path,
    width: int,
    capture: dict[str, str] | None,
) -> ImportResult:
    fields: dict[str, object] = {} if capture is None else {"capture": capture}
    return import_clip(media, write_recording, data_root, width, **fields)


def _groups(members: tuple[ImportResult, ...], *, case: bool) -> list[dict[str, object]]:
    omitted, repeated, another, steered, airborne = members
    omitted_stream = stream_of(omitted, stream_id="omit")
    if case:
        omitted_stream = omitted_stream | {
            "generated_cases": [case_of("omit-shake", "camera_shake", 3, _SHAKE)]
        }
    return [
        group_of(
            "site",
            "development",
            encounter_of("enc-omit", omitted_stream),
            encounter_of(
                "enc-repeat",
                stream_of(repeated, stream_id="repeat-a", selection=HEAD),
                stream_of(repeated, stream_id="repeat-b", selection=TAIL),
            ),
            encounter_of("enc-second", stream_of(another, stream_id="second")),
            encounter_of(
                "enc-mixed",
                stream_of(steered, stream_id="steered"),
                stream_of(airborne, stream_id="airborne"),
            ),
        )
    ]


def _historical_capture(path: Path) -> bytes:
    record = json.loads(path.read_text(encoding="ascii"))
    capture = dict(record["capture"])
    capture["camera_control_mode"] = "gimbal"
    del capture["observer_platform"]
    reseal(path, schema_version=2, capture=capture)
    return path.read_bytes()
