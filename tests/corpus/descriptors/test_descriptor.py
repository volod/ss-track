"""Dataset descriptions are reproducible, loadable and fail closed for public views."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import build_corpus, import_source, stage_corpus
from ss_track.corpus.descriptors.descriptor import describe_corpus
from tests.corpus.conftest import WriteCorpus, WriteRecording, case_of, reseal, stream_of


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


@pytest.fixture
def staged(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> Path:
    imported = import_source(write_recording(), data_root)
    case = case_of("blurred", "blur", 1, {"max_radius": 2})
    manifest = write_corpus([stream_of(imported, generated_cases=[case])])
    build_corpus(manifest, data_root)
    stage_corpus("pilot-v1", data_root)
    return data_root


def _rows(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return [json.loads(row["record"]) for row in csv.DictReader(handle)]


def test_descriptor_contains_sealed_facts_and_is_deterministic(
    staged: Path, declaration: Path
) -> None:
    result = describe_corpus("pilot-v1", declaration, staged)
    directory = result.manifest_path.parent
    first = {
        p.relative_to(directory).as_posix(): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }
    assert describe_corpus("pilot-v1", declaration, staged) == result
    assert first == {
        p.relative_to(directory).as_posix(): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }
    from ss_track.schema.registry.store import load_contract_set

    copied = load_contract_set(directory / "contracts")
    assert copied.named("record/frame-bundle").versions[-1].version == "3.1.0"
    assert (copied.root / "meta/standards/odcs-3.2.0.json").is_file()
    assert (copied.root / "meta/standards/ODCS-LICENSE.txt").is_file()
    streams = _rows(directory / "streams.csv")
    bundles = _rows(directory / "bundles.csv")
    frames = _rows(directory / "frames.csv")
    assert streams[0]["stream"]["rights"]["sharing"] == "restricted"
    assert len(bundles) == 2
    assert {row["generated"] for row in frames} == {False, True}
    assert all((directory / row["path"]).is_file() for row in frames)
    assert "do not count as encounters" in (directory / "dataset-card.md").read_text()


def test_public_refusal_does_not_disclose_values(staged: Path, declaration: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged, "public")
    assert caught.value.code == RefusalCode.RIGHTS_CONFLICT
    assert caught.value.details == {}
    assert "pilot-v1" not in str(caught.value)
    assert not (staged / "corpus/pilot-v1/descriptions/public").exists()


def test_missing_license_is_refused_without_disclosure(staged: Path, declaration: Path) -> None:
    document = yaml.safe_load(declaration.read_text())
    del document["license"]
    declaration.write_text(yaml.safe_dump(document))
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged)
    assert caught.value.code == RefusalCode.MANIFEST_INVALID


def test_croissant_loads_all_record_sets(staged: Path, declaration: Path) -> None:
    mlc = pytest.importorskip("mlcroissant")
    result = describe_corpus("pilot-v1", declaration, staged)
    dataset = mlc.Dataset(str(result.manifest_path))
    for name in ("streams", "bundles", "frames"):
        loaded = list(dataset.records(f"{name}-records"))
        assert len(loaded) == len(_rows(result.manifest_path.parent / f"{name}.csv"))
        assert loaded


def test_public_view_counts_locked_without_disclosing_records(
    clip: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    declaration: Path,
) -> None:
    from tests.corpus.conftest import encounter_of, group_of, recording_declaration

    rights = recording_declaration()["rights"] | {"sharing": "public", "holder": "secret-holder"}
    imported = import_source(write_recording(rights=rights), data_root)
    stream = stream_of(imported, stream_id="secret-stream")
    group = group_of("secret-group", "locked", encounter_of("secret-encounter", stream))
    manifest = write_grouped_corpus(
        [group], scenario_rights={"sharing": "public", "max_sensitivity": "high"}
    )
    build_corpus(manifest, data_root)
    stage_corpus("pilot-v1", data_root)
    result = describe_corpus("pilot-v1", declaration, data_root, "public")
    directory = result.manifest_path.parent
    for name in ("streams", "bundles", "frames"):
        assert _rows(directory / f"{name}.csv") == []
    output = b"".join(path.read_bytes() for path in directory.rglob("*") if path.is_file())
    for secret in (
        b"secret-holder",
        b"secret-stream",
        b"secret-group",
        b"secret-encounter",
        imported.source_sha256.encode(),
    ):
        assert secret not in output
    assert '"streams": 1' in (directory / "dataset-card.md").read_text()
    if importlib.util.find_spec("mlcroissant") is not None:
        import mlcroissant as mlc

        dataset = mlc.Dataset(str(result.manifest_path))
        for name in ("streams", "bundles", "frames"):
            assert list(dataset.records(f"{name}-records")) == []
    document = yaml.safe_load(declaration.read_text())
    document.pop("license")
    declaration.write_text(yaml.safe_dump(document))
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, data_root, "public")
    assert caught.value.code == RefusalCode.MANIFEST_INVALID
    assert caught.value.details == {}
    assert str(caught.value) == "dataset declaration is invalid"


def test_cli_describe_and_refusal(
    staged: Path, declaration: Path, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from ss_track.cli import main

    assert (
        main(["corpus", "describe", "--corpus", "pilot-v1", "--declaration", str(declaration)]) == 0
    )
    assert json.loads(caplog.records[-1].getMessage())["status"] == "recorded"
    caplog.clear()
    assert (
        main(
            [
                "corpus",
                "describe",
                "--corpus",
                "pilot-v1",
                "--declaration",
                str(declaration),
                "--visibility",
                "public",
            ]
        )
        == 1
    )
    refusal = json.loads(caplog.records[-1].getMessage())
    assert refusal["code"] == "RIGHTS_CONFLICT"
    assert "pilot-v1" not in caplog.records[-1].getMessage()


def test_damaged_frame_refuses_without_creating_descriptor(staged: Path, declaration: Path) -> None:
    frame = next((staged / "corpus/pilot-v1/frames/one").glob("*.rgb24"))
    frame.chmod(0o644)
    frame.write_bytes(b"damaged")
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged)
    assert caught.value.code == RefusalCode.FRAME_CORRUPTED
    assert not (staged / "corpus/pilot-v1/descriptions").exists()


def test_source_replaced_after_verification_is_not_exported(
    staged: Path, declaration: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ss_track.corpus.descriptors import descriptor

    load = descriptor.load_source_record

    def changed(source_sha256: str, root: Path) -> dict:
        return load(source_sha256, root) | {"manifest_sha256": "0" * 64}

    monkeypatch.setattr(descriptor, "load_source_record", changed)
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged)
    assert caught.value.code == RefusalCode.SOURCE_RECORD_CHANGED
    assert not (staged / "corpus/pilot-v1/descriptions").exists()


def test_bundle_index_changed_after_verification_is_not_exported(
    staged: Path, declaration: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ss_track.corpus.descriptors import descriptor

    verify = descriptor.verify_corpus_frames

    def verified_then_changed(corpus_id: str, data_root: Path) -> object:
        result = verify(corpus_id, data_root)
        reseal(data_root / "corpus/pilot-v1/frames/one/manifest.json", bundle_sha256="0" * 64)
        return result

    monkeypatch.setattr(descriptor, "verify_corpus_frames", verified_then_changed)
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged)
    assert caught.value.code == RefusalCode.RECORD_TAMPERED
    assert caught.value.message == "bundle hash does not cover this frame index"
    assert not (staged / "corpus/pilot-v1/descriptions").exists()
