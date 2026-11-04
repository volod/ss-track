"""A corrected declaration replaces one descriptor and leaves sealed evidence in place."""

import json
from pathlib import Path

import pytest
import yaml

from ss_track.corpus import build_corpus, import_source, stage_corpus
from ss_track.corpus.descriptor import describe_corpus
from ss_track.refusal import CorpusRefusal, RefusalCode
from tests.corpus.conftest import WriteCorpus, WriteRecording, case_of, stream_of


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


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _sealed(root: Path) -> dict[str, bytes]:
    corpus = root / "corpus" / "pilot-v1"
    return {
        path.relative_to(corpus).as_posix(): path.read_bytes()
        for path in corpus.rglob("*")
        if path.is_file() and "descriptions" not in path.relative_to(corpus).parts
    }


def test_corrected_declaration_replaces_the_descriptor(staged: Path, declaration: Path) -> None:
    result = describe_corpus("pilot-v1", declaration, staged)
    directory = result.manifest_path.parent
    previous = _files(directory)
    evidence = _sealed(staged)
    document = yaml.safe_load(declaration.read_text())
    document["title"] = "Corrected"
    document["license"] = "https://example.org/corrected"
    declaration.write_text(yaml.safe_dump(document))
    refreshed = describe_corpus("pilot-v1", declaration, staged)
    metadata = json.loads(refreshed.manifest_path.read_text())
    assert refreshed == result
    assert metadata["name"] == "Corrected"
    assert metadata["license"] == "https://example.org/corrected"
    assert (directory / "dataset-card.md").read_text().startswith("# Corrected\n")
    frames = (directory / "frames.csv").read_text()
    assert "00000000.rgb24" in frames
    published = _files(directory)
    assert published != previous
    assert b"https://example.org/license" not in refreshed.manifest_path.read_bytes()
    inode = refreshed.manifest_path.stat().st_ino
    assert describe_corpus("pilot-v1", declaration, staged) == refreshed
    assert refreshed.manifest_path.stat().st_ino == inode
    assert _files(directory) == published
    assert _sealed(staged) == evidence
    parent = directory.parent
    assert not (parent / ".replaced-restricted").exists()
    assert list(parent.glob(".incoming-*")) == []
    assert not (parent / "public").exists()


def test_a_refusal_does_not_replace_the_descriptor(staged: Path, declaration: Path) -> None:
    result = describe_corpus("pilot-v1", declaration, staged)
    directory = result.manifest_path.parent
    snapshot = _files(directory)
    inode = result.manifest_path.stat().st_ino
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged, "public")
    assert caught.value.code == RefusalCode.RIGHTS_CONFLICT
    assert caught.value.details == {}
    document = yaml.safe_load(declaration.read_text())
    document.pop("license")
    declaration.write_text(yaml.safe_dump(document))
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged)
    assert caught.value.code == RefusalCode.MANIFEST_INVALID
    document["license"] = "https://example.org/license"
    declaration.write_text(yaml.safe_dump(document))
    frame = next((staged / "corpus/pilot-v1/frames/one").glob("*.rgb24"))
    frame.chmod(0o644)
    frame.write_bytes(b"damaged")
    with pytest.raises(CorpusRefusal) as caught:
        describe_corpus("pilot-v1", declaration, staged)
    assert caught.value.code == RefusalCode.FRAME_CORRUPTED
    assert _files(directory) == snapshot
    assert result.manifest_path.stat().st_ino == inode
    assert not (directory.parent / ".replaced-restricted").exists()
    assert not (directory.parent / "public").exists()
