"""Explicit sequences use the ordinary corpus import, stage and integrity boundaries."""

from pathlib import Path

import pytest
import yaml

from ss_track.core.evidence.sealing import sha256_file
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import (
    amend_source,
    build_corpus,
    import_source,
    redecode_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.siblings.video_hints import MISSING_TIMESTAMPS, StreamTiming
from ss_track.corpus.sources.stored import load_verified_source
from ss_track.corpus.versions.near_duplicate_samples import sampled_frames
from tests.corpus._images import image
from tests.corpus.conftest import WriteCorpus, recording_declaration, stream_of


def declaration(root: Path, rate: str | None = None) -> Path:
    paths = [image(root / f"{index}.png", index) for index in range(4)]
    body = recording_declaration(".")
    source = {
        "path": ".",
        "frames": [
            {"index": i, "path": path.name, "sha256": sha256_file(path)}
            for i, path in enumerate(paths)
        ],
    }
    if rate is not None:
        source["frame_rate"] = rate
    body["source"] = source
    path = root / "recording.yaml"
    path.write_text(yaml.safe_dump(body), encoding="ascii")
    return path


@pytest.mark.parametrize("rate", [None, "25", "30000/1001", "1"])
def test_sequence_import_build_stage_repeats(
    media: Path, data_root: Path, write_corpus: WriteCorpus, rate: str | None
) -> None:
    path = declaration(media, rate)
    first = import_source(path, data_root)
    second = import_source(path, data_root)
    assert first.source_sha256 == second.source_sha256
    assert first.manifest_sha256 == second.manifest_sha256
    assert second.status == "unchanged"
    assert first.timestamp_quality == ("missing" if rate is None else "derived")
    build_corpus(write_corpus([stream_of(first)]), data_root)
    staged = stage_corpus("pilot-v1", data_root)
    repeated = stage_corpus("pilot-v1", data_root)
    assert staged.bundles[0].bundle_sha256 == repeated.bundles[0].bundle_sha256
    assert verify_corpus_frames("pilot-v1", data_root).status == "verified"
    assert redecode_source(path, data_root).status == "unchanged"
    assert amend_source(path, data_root).status == "unchanged"
    verified = load_verified_source(first.source_sha256, data_root)
    assert sampled_frames(first.source_sha256, [(0, 4)], data_root)
    timing = StreamTiming("one", first.source_sha256, 0, 4, verified.sequence)
    assert timing.unmappable() == (MISSING_TIMESTAMPS if rate is None else None)
    image_path = verified.stored / "00000001.png"
    image_path.chmod(0o644)
    image_path.write_bytes(b"changed")
    with pytest.raises(CorpusRefusal) as error:
        load_verified_source(first.source_sha256, data_root)
    assert error.value.code == RefusalCode.SOURCE_HASH_MISMATCH
    assert "00000001.png" in str(error.value)


@pytest.mark.parametrize("damage", ["gap", "changed", "mixed", "missing"])
def test_bad_sequence_is_refused(media: Path, data_root: Path, damage: str) -> None:
    path = declaration(media)
    body = yaml.safe_load(path.read_text())
    if damage == "gap":
        body["source"]["frames"][1]["index"] = 2
    elif damage == "changed":
        image(media / "1.png", 99)
    elif damage == "mixed":
        image(media / "1.png", 1, width=6)
        body["source"]["frames"][1]["sha256"] = sha256_file(media / "1.png")
    else:
        (media / "1.png").unlink()
    path.write_text(yaml.safe_dump(body), encoding="ascii")
    with pytest.raises(CorpusRefusal) as error:
        import_source(path, data_root)
    assert "1.png" in str(error.value) or "index 1" in str(error.value)


def test_rate_conflict_and_amendment_without_original_images(media: Path, data_root: Path) -> None:
    path = declaration(media, "25")
    first = import_source(path, data_root)
    body = yaml.safe_load(path.read_text())
    body["source"]["frame_rate"] = "30"
    path.write_text(yaml.safe_dump(body), encoding="ascii")
    with pytest.raises(CorpusRefusal) as error:
        import_source(path, data_root)
    assert error.value.code == RefusalCode.IMPORT_CONFLICT
    body["source"]["frame_rate"] = "25"
    path.write_text(yaml.safe_dump(body), encoding="ascii")
    for original in media.glob("*.png"):
        original.unlink()
    assert amend_source(path, data_root).source_sha256 == first.source_sha256
    assert redecode_source(path, data_root).status == "unchanged"


@pytest.mark.parametrize("damage", ["missing", "inventory", "extra"])
def test_retained_membership_is_pinned(media: Path, data_root: Path, damage: str) -> None:
    imported = import_source(declaration(media), data_root)
    stored = load_verified_source(imported.source_sha256, data_root).stored
    if damage == "missing":
        (stored / "00000001.png").unlink()
    elif damage == "extra":
        (stored / "extra.png").write_bytes(b"extra")
    else:
        index = stored / "index.json"
        index.chmod(0o644)
        index.write_text("{}", encoding="ascii")
    with pytest.raises(CorpusRefusal) as error:
        load_verified_source(imported.source_sha256, data_root)
    assert error.value.code == RefusalCode.SOURCE_HASH_MISMATCH
    if damage == "missing":
        assert "image not found: 00000001.png" in str(error.value)
    elif damage == "extra":
        assert "sequence membership changed" in str(error.value)


def test_lossy_image_is_refused_even_with_png_filename(media: Path, data_root: Path) -> None:
    path = declaration(media)
    body = yaml.safe_load(path.read_text())
    image(media / "1.png", 3, codec="mjpeg", pixel_format="yuvj444p")
    body["source"]["frames"][1]["sha256"] = sha256_file(media / "1.png")
    path.write_text(yaml.safe_dump(body), encoding="ascii")
    with pytest.raises(CorpusRefusal) as error:
        import_source(path, data_root)
    assert error.value.code == RefusalCode.SOURCE_UNREADABLE
    assert "00000001.png" in str(error.value)


@pytest.mark.parametrize("field", ["capture_clock", "video_stream", "duplicate"])
def test_unsupported_sequence_claims_are_refused(media: Path, data_root: Path, field: str) -> None:
    path = declaration(media)
    body = yaml.safe_load(path.read_text())
    if field == "capture_clock":
        body["timestamps"] = {"capture_clock_evidence": "hardware clock"}
    elif field == "video_stream":
        body["source"]["video_stream_index"] = 0
    else:
        body["source"]["frames"][1]["path"] = "0.png"
    path.write_text(yaml.safe_dump(body), encoding="ascii")
    with pytest.raises(CorpusRefusal) as error:
        import_source(path, data_root)
    assert error.value.code == RefusalCode.MANIFEST_INVALID
