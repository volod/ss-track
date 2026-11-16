"""`ss-track annotate derive` on one built corpus.

The shake offset comes from the stored case. The expected box is clipped by hand from
the parent box `(1, 2, 4, 3)`. An unscorable case is not a zero, and a later refusal
does not replace files already written.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.revision import read_annotation_revision
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.core.canonical import SEAL_FIELD, canonical_json, sha256_bytes
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import RefusalCode
from ss_track.corpus.records.kinds import CORPUS_MANIFEST, DERIVED_LABEL
from ss_track.corpus.storage.layout import corpus_manifest_path, label_document_path
from tests.annotate.derived_corpus import (
    CORPUS,
    STREAM,
    assert_command,
    copy_data,
    derive,
    install_labels,
)
from tests.annotate.documents import load_labels
from tests.corpus.conftest import reseal


def test_a_parent_without_frozen_labels_is_unscorable(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = copy_data(built[0], tmp_path)
    record = derive(data, monkeypatch, caplog)

    assert record["status"] == "derived"
    cases = record["label_derivation"]["cases"]
    assert [item["status"] for item in cases] == ["unscorable", "unscorable"]
    assert {item["reason"] for item in cases} == {"no_frozen_labels"}
    assert all(set(item) == {"case_id", "status", "reason"} for item in cases)
    assert not (data / "corpus" / CORPUS / "labels").exists()
    assert_command(record)


def test_derive_seals_the_hand_clipped_box(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    pack: ScenarioPack,
) -> None:
    data, clip, folder = built
    copied = copy_data(data, tmp_path)
    install_labels(copied, folder)
    record = derive(copied, monkeypatch, caplog)
    space = read_frame_space(clip)
    manifest = read_sealed(corpus_manifest_path(copied, CORPUS), CORPUS_MANIFEST)
    shake = _named(manifest, "shake")
    offset = next(item for item in shake["label_transform"]["offsets"] if item["frame_index"] == 0)
    expected = _clip(1, 2, 4, 3, int(offset["dx"]), int(offset["dy"]), space.width, space.height)
    derived = load_labels(label_document_path(copied, CORPUS, "shake"), pack, space)
    sealed = read_sealed(
        label_document_path(copied, CORPUS, "shake").with_name("revision.json"), DERIVED_LABEL
    )
    parent = read_annotation_revision(
        copied / "corpus" / CORPUS / "labels" / STREAM / "revision.json"
    )

    assert derived.label_id == "shake"
    assert derived.instances[0].frames[0].geometry.box is not None
    box = derived.instances[0].frames[0].geometry.box
    assert (box.x, box.y, box.width, box.height) == expected
    assert derived.instances[0].frames[0].camera_motion == "shake"
    assert derived.instances[0].frames[0].annotator_id == "ada"
    absence = load_labels(label_document_path(copied, CORPUS, "absence"), pack, space)
    kept = absence.instances[0].frames[0].geometry.box
    assert kept is not None
    assert (kept.x, kept.y, kept.width, kept.height) == (1, 2, 4, 3)
    assert sealed["transform_kind"] == "translate"
    assert sealed["timestamp_quality"] is None
    assert sealed["parent_revision_sha256"] == parent[SEAL_FIELD]
    assert sealed["label_transform_sha256"] == sha256_bytes(
        canonical_json(shake["label_transform"])
    )
    assert record["label_derivation"]["cases"][1]["timestamp_quality"] is None
    assert_command(record)


def test_a_later_refusal_keeps_the_files_already_written(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data, _clip, folder = built
    copied = copy_data(data, tmp_path)
    install_labels(copied, folder)
    assert derive(copied, monkeypatch, caplog)["status"] == "derived"
    before = _case_bytes(copied)
    _cover_the_plate(corpus_manifest_path(copied, CORPUS))
    refused = derive(copied, monkeypatch, caplog, code=1)

    assert refused["code"] == RefusalCode.MANIFEST_INVALID
    assert "plate frame 0 shows a target inside the region" in str(refused["message"])
    assert _case_bytes(copied) == before


def test_a_tampered_revision_and_a_changed_label_leave_those_files(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data, _clip, folder = built
    copied = copy_data(data, tmp_path)
    install_labels(copied, folder)
    derive(copied, monkeypatch, caplog)
    before = _case_bytes(copied)
    revision = copied / "corpus" / CORPUS / "labels" / STREAM / "revision.json"
    revision.chmod(0o644)
    sealed = json.loads(revision.read_text(encoding="ascii"))
    digest = str(sealed["manifest_sha256"])
    sealed["manifest_sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
    revision.write_text(json.dumps(sealed), encoding="ascii")
    tampered = derive(copied, monkeypatch, caplog, code=1)
    assert tampered["code"] == RefusalCode.RECORD_TAMPERED
    assert _case_bytes(copied) == before

    fresh = copy_data(data, tmp_path / "fresh")
    install_labels(fresh, folder)
    derive(fresh, monkeypatch, caplog)
    saved = _case_bytes(fresh)
    document = fresh / "corpus" / CORPUS / "labels" / STREAM / "labels.json"
    document.chmod(0o644)
    body = json.loads(document.read_text(encoding="ascii"))
    body["instances"][0]["frames"][0]["geometry"]["box"]["width"] = 5
    document.write_text(json.dumps(body), encoding="ascii")
    mismatched = derive(fresh, monkeypatch, caplog, code=1)
    assert mismatched["code"] == RefusalCode.MANIFEST_INVALID
    assert "label document does not match the frozen revision" in str(mismatched["message"])
    assert _case_bytes(fresh) == saved


def test_a_corpus_with_no_cases_derives_nothing(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    copied = copy_data(built[0], tmp_path)
    reseal(corpus_manifest_path(copied, CORPUS), generated_cases=[])
    record = derive(copied, monkeypatch, caplog)

    assert record["label_derivation"] == {"corpus_id": CORPUS, "cases": []}
    assert_command(record)


def _case_bytes(data: Path) -> dict[str, bytes]:
    root = data / "corpus" / CORPUS / "labels"
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.parent.name != STREAM and path.name != ".derive.lock"
    }


def _cover_the_plate(path: Path) -> None:
    record = json.loads(path.read_text(encoding="ascii"))
    cases = copy.deepcopy(record["generated_cases"])
    for case in cases:
        transform = case["label_transform"]
        if transform["kind"] == "region_status":
            transform["region"] = {"x": 0, "y": 0, "width": 20, "height": 20}
    reseal(path, generated_cases=cases)


def _named(manifest: dict[str, Any], case_id: str) -> dict[str, Any]:
    found = next(item for item in manifest["generated_cases"] if item["case_id"] == case_id)
    if not isinstance(found, dict):
        raise TypeError("generated case is not an object")
    return found


def _clip(
    x: int, y: int, width: int, height: int, dx: int, dy: int, frame_width: int, frame_height: int
) -> tuple[int, int, int, int]:
    left, top = max(0, x + dx), max(0, y + dy)
    right, bottom = min(frame_width, x + dx + width), min(frame_height, y + dy + height)
    if right <= left or bottom <= top:
        raise AssertionError("the stored offset pushed the box out of the frame")
    return (left, top, right - left, bottom - top)
