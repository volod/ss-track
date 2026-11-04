"""A public descriptor publishes reviewed fields and withholds locked sequences."""

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.corpus import build_corpus, import_source, stage_corpus
from ss_track.corpus.descriptor import describe_corpus
from ss_track.corpus.frame_set import frame_set_path
from ss_track.corpus.importer import ImportResult
from ss_track.corpus.sources import load_source_record
from ss_track.schema.store import load_contract_set
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    encounter_of,
    group_of,
    recording_declaration,
    stream_of,
)


def _rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        return [json.loads(row["record"]) for row in csv.DictReader(handle)]


@pytest.fixture
def declaration(tmp_path: Path) -> Path:
    path = tmp_path / "dataset.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "title": "Example",
                "description": "Example data",
                "license": "https://example.org/license",
                "citation": "Example citation",
                "address": "https://example.org/dataset",
                "publication_date": "2024-01-01",
            }
        )
    )
    return path


def _import(
    media: Path,
    write_recording: WriteRecording,
    data_root: Path,
    name: str,
    width: int,
    marker: str,
) -> ImportResult:
    from tests.corpus._media import write_clip

    write_clip(media / name, width=width)
    rights = recording_declaration()["rights"] | {
        "sharing": "public",
        "holder": f"hidden-{marker}-holder",
        "retention": f"hidden-{marker}-retention",
    }
    return import_source(
        write_recording(
            name,
            rights=rights,
            sensitivity={"level": "low", "notes": f"hidden-{marker}-note"},
            capture={"camera": f"hidden-{marker}-camera"},
        ),
        data_root,
    )


def test_public_descriptor_projects_non_locked_fields(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    declaration: Path,
) -> None:
    opened = _import(media, write_recording, data_root, "hidden-open-source.mkv", 64, "open")
    locked = _import(media, write_recording, data_root, "hidden-locked-source.mkv", 66, "locked")
    manifest = write_grouped_corpus(
        _groups(opened, locked),
        scenario_rights={"sharing": "public", "max_sensitivity": "high"},
    )
    build_corpus(manifest, data_root)
    stage_corpus("pilot-v1", data_root)
    result = describe_corpus("pilot-v1", declaration, data_root, "public")
    assert describe_corpus("pilot-v1", declaration, data_root, "public") == result
    _assert_public(result, opened, locked, data_root)


def _groups(opened: ImportResult, locked: ImportResult) -> list[dict[str, Any]]:
    opened_stream = stream_of(
        opened,
        stream_id="open-stream",
        generated_cases=[case_of("open-blur", "blur", 7, {"max_radius": 17})],
    )
    locked_stream = stream_of(
        locked,
        stream_id="locked-stream",
        generated_cases=[case_of("locked-case", "blur", 9, {"max_radius": 19})],
    )
    return [
        group_of("open-group", "development", encounter_of("open-encounter", opened_stream)),
        group_of("locked-group", "locked", encounter_of("locked-encounter", locked_stream)),
    ]


def _assert_public(
    result: Any, opened: ImportResult, locked: ImportResult, data_root: Path
) -> None:
    directory = result.manifest_path.parent
    disclosed = _disclosed(directory)
    _assert_rows(directory, disclosed)
    _assert_secrets(disclosed, opened, locked, data_root)
    _assert_contracts(directory)
    _assert_croissant(result.manifest_path)


def _disclosed(directory: Path) -> bytes:
    return b"".join(
        path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "contracts/" not in path.relative_to(directory).as_posix()
    )


def _assert_rows(directory: Path, disclosed: bytes) -> None:
    streams = _rows(directory / "streams.csv")
    bundles = _rows(directory / "bundles.csv")
    frames = _rows(directory / "frames.csv")
    assert {row["stream"]["stream_id"] for row in streams} == {"open-stream"}
    assert streams[0]["stream"]["rights"] == {
        "basis": "owned",
        "sharing": "public",
        "derived_frames": True,
        "retain_until": None,
    }
    assert streams[0]["stream"]["sensitivity"] == {"level": "low"}
    assert streams[0]["scenario_rights"]["max_sensitivity"] == "high"
    text = disclosed.decode()
    assert "sha256_declared" not in text
    assert "decoder_version" not in text
    assert "size_bytes" not in text
    blur = next(row for row in bundles if row["stream_id"] == "open-blur")
    original = next(row for row in bundles if row["stream_id"] == "open-stream")
    assert blur["identity"]["recipe"]["parameters"] == {"max_radius": 17}
    assert original["generated"] is None
    assert blur["generated"]["parent_stream_id"] == "open-stream"
    assert {row["stream_id"] for row in bundles} == {"open-stream", "open-blur"}
    assert all((directory / row["path"]).is_file() for row in frames)
    assert {row["stream_id"] for row in frames} == {"open-stream", "open-blur"}
    assert {row["generated"] for row in frames if row["stream_id"] == "open-stream"} == {False}
    assert {row["generated"] for row in frames if row["stream_id"] == "open-blur"} == {True}


def _assert_secrets(
    disclosed: bytes, opened: ImportResult, locked: ImportResult, data_root: Path
) -> None:
    source = load_source_record(opened.source_sha256, data_root)
    frame_set = json.loads(frame_set_path(data_root, "pilot-v1").read_text(encoding="ascii"))
    withheld = [
        "hidden-open-holder",
        "hidden-locked-holder",
        "hidden-open-note",
        "hidden-locked-note",
        "hidden-open-retention",
        "hidden-locked-retention",
        "hidden-open-camera",
        "hidden-locked-camera",
        "hidden-open-source.mkv",
        "hidden-locked-source.mkv",
        "locked-stream",
        "locked-group",
        "locked-encounter",
        "locked-case",
        source["source"]["sha256"],
        locked.source_sha256,
    ]
    withheld.extend(_bundle_hashes(frame_set))
    for secret in withheld:
        assert secret.encode() not in disclosed


def _bundle_hashes(frame_set: dict[str, Any]) -> list[str]:
    watched = {"open-stream", "locked-stream", "open-blur", "locked-case"}
    return [
        bundle["bundle_sha256"] for bundle in frame_set["bundles"] if bundle["stream_id"] in watched
    ]


def _assert_contracts(directory: Path) -> None:
    copied = load_contract_set(directory / "contracts")
    assert copied.named("record/corpus-manifest").versions[-1].version == "3.1.0"
    assert copied.named("record/source-manifest").versions[-1].version == "2.1.0"
    assert copied.named("record/frame-bundle").versions[-1].version == "3.1.0"


def _assert_croissant(manifest: Path) -> None:
    if importlib.util.find_spec("mlcroissant") is None:
        return
    import mlcroissant as mlc

    dataset = mlc.Dataset(str(manifest))
    assert list(dataset.records("streams-records"))
    assert list(dataset.records("frames-records"))
