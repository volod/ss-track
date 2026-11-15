"""`ss-track annotate derive` on one built corpus.

The shake offset comes from the stored case. The expected box is clipped by hand from
the parent box `(1, 2, 4, 3)`. An unscorable case is not a zero, and a later refusal
does not replace files already written.
"""

import copy
import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.annotate.compare import compare_label_sets
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.revision_record import read_annotation_revision
from ss_track.annotate.space import read_frame_space
from ss_track.cli import main
from ss_track.core.canonical import SEAL_FIELD, canonical_json, sha256_bytes
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import RefusalCode
from ss_track.corpus import build_corpus, import_source
from ss_track.corpus.records.kinds import CORPUS_MANIFEST, DERIVED_LABEL
from ss_track.corpus.storage.layout import corpus_manifest_path, label_document_path
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations
from tests.annotate.documents import load_labels
from tests.annotate.review_files import (
    decision_for,
    freeze_written,
    prepare_pair,
    write_review,
    write_settlement,
)
from tests.annotate.support import DRAFT
from tests.corpus._media import write_clip
from tests.corpus.conftest import (
    case_of,
    encounter_of,
    group_of,
    recording_declaration,
    reseal,
    stream_of,
    write_groups,
)

_CORPUS = "pilot-v1"
_STREAM = "one"
_AWAY = {"x": 40, "y": 30, "width": 10, "height": 10}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory, pack: ScenarioPack) -> tuple[Path, Path, Path]:
    """Import one clip, build a shake and an absence case, and freeze the parent labels."""
    root = tmp_path_factory.mktemp("derive-built")
    media = root / "media"
    media.mkdir()
    clip = write_clip(media / "clip.mkv")
    recording = media / "recording.yaml"
    recording.write_text(yaml.safe_dump(recording_declaration()), encoding="utf-8")
    data = root / "data"
    imported = import_source(recording, data)
    absence = case_of(
        "absence", "target_absence", 1, {"region": _AWAY, "plate_frame": 0, "noise": 2}
    )
    shake = case_of("shake", "camera_shake", 1, {"amplitude": 2})
    stream = stream_of(imported, generated_cases=[absence, shake])
    groups = [group_of("group-one", "development", encounter_of("enc-one", stream))]
    build_corpus(write_groups(media, groups), data)
    folder = root / "frozen"
    left, right = prepare_pair(folder, pack, clip, lambda _body: None)
    write_review(folder)
    write_settlement(folder, [decision_for(row, "left") for row in compare_label_sets(left, right)])
    freeze_written(folder, clip)
    return data, clip, folder


def test_a_parent_without_frozen_labels_is_unscorable(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = _copy(built[0], tmp_path)
    record = _derive(data, monkeypatch, caplog)

    assert record["status"] == "derived"
    cases = record["label_derivation"]["cases"]
    assert [item["status"] for item in cases] == ["unscorable", "unscorable"]
    assert {item["reason"] for item in cases} == {"no_frozen_labels"}
    assert all(set(item) == {"case_id", "status", "reason"} for item in cases)
    assert not (data / "corpus" / _CORPUS / "labels").exists()
    _assert_command(record)


def test_derive_seals_the_hand_clipped_box(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    pack: ScenarioPack,
) -> None:
    data, clip, folder = built
    copied = _copy(data, tmp_path)
    _install(copied, folder)
    record = _derive(copied, monkeypatch, caplog)
    space = read_frame_space(clip)
    manifest = read_sealed(corpus_manifest_path(copied, _CORPUS), CORPUS_MANIFEST)
    shake = _named(manifest, "shake")
    offset = next(item for item in shake["label_transform"]["offsets"] if item["frame_index"] == 0)
    expected = _clip(1, 2, 4, 3, int(offset["dx"]), int(offset["dy"]), space.width, space.height)
    derived = load_labels(label_document_path(copied, _CORPUS, "shake"), pack, space)
    sealed = read_sealed(
        label_document_path(copied, _CORPUS, "shake").with_name("revision.json"), DERIVED_LABEL
    )
    parent = read_annotation_revision(
        copied / "corpus" / _CORPUS / "labels" / _STREAM / "revision.json"
    )

    assert derived.label_id == "shake"
    assert derived.instances[0].frames[0].geometry.box is not None
    box = derived.instances[0].frames[0].geometry.box
    assert (box.x, box.y, box.width, box.height) == expected
    assert derived.instances[0].frames[0].camera_motion == "shake"
    assert derived.instances[0].frames[0].annotator_id == "ada"
    absence = load_labels(label_document_path(copied, _CORPUS, "absence"), pack, space)
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
    _assert_command(record)


def test_a_later_refusal_keeps_the_files_already_written(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data, _clip, folder = built
    copied = _copy(data, tmp_path)
    _install(copied, folder)
    assert _derive(copied, monkeypatch, caplog)["status"] == "derived"
    before = _case_bytes(copied)
    _cover_the_plate(corpus_manifest_path(copied, _CORPUS))
    refused = _derive(copied, monkeypatch, caplog, code=1)

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
    copied = _copy(data, tmp_path)
    _install(copied, folder)
    _derive(copied, monkeypatch, caplog)
    before = _case_bytes(copied)
    revision = copied / "corpus" / _CORPUS / "labels" / _STREAM / "revision.json"
    revision.chmod(0o644)
    sealed = json.loads(revision.read_text(encoding="ascii"))
    digest = str(sealed["manifest_sha256"])
    sealed["manifest_sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
    revision.write_text(json.dumps(sealed), encoding="ascii")
    tampered = _derive(copied, monkeypatch, caplog, code=1)
    assert tampered["code"] == RefusalCode.RECORD_TAMPERED
    assert _case_bytes(copied) == before

    fresh = _copy(data, tmp_path / "fresh")
    _install(fresh, folder)
    _derive(fresh, monkeypatch, caplog)
    saved = _case_bytes(fresh)
    document = fresh / "corpus" / _CORPUS / "labels" / _STREAM / "labels.json"
    document.chmod(0o644)
    body = json.loads(document.read_text(encoding="ascii"))
    body["instances"][0]["frames"][0]["geometry"]["box"]["width"] = 5
    document.write_text(json.dumps(body), encoding="ascii")
    mismatched = _derive(fresh, monkeypatch, caplog, code=1)
    assert mismatched["code"] == RefusalCode.MANIFEST_INVALID
    assert "label document does not match the frozen revision" in str(mismatched["message"])
    assert _case_bytes(fresh) == saved


def test_a_corpus_with_no_cases_derives_nothing(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    copied = _copy(built[0], tmp_path)
    reseal(corpus_manifest_path(copied, _CORPUS), generated_cases=[])
    record = _derive(copied, monkeypatch, caplog)

    assert record["label_derivation"] == {"corpus_id": _CORPUS, "cases": []}
    _assert_command(record)


def _derive(
    data: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, *, code: int = 0
) -> dict[str, Any]:
    caplog.set_level(logging.INFO)
    caplog.clear()
    monkeypatch.setenv("DATA_DIR", str(data))
    assert main(["annotate", "derive", "--corpus", _CORPUS, "--pack", str(DRAFT)]) == code
    loaded = json.loads(caplog.records[-1].getMessage())
    if not isinstance(loaded, dict):
        raise TypeError("command record is not an object")
    return loaded


def _install(data: Path, folder: Path) -> None:
    dest = data / "corpus" / _CORPUS / "labels" / _STREAM
    dest.mkdir(parents=True)
    shutil.copy(folder / "frozen.json", dest / "labels.json")
    shutil.copy(folder / "revision.json", dest / "revision.json")


def _copy(source: Path, dest: Path) -> Path:
    copied = dest / "data"
    shutil.copytree(source, copied)
    return copied


def _case_bytes(data: Path) -> dict[str, bytes]:
    root = data / "corpus" / _CORPUS / "labels"
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.parent.name != _STREAM and path.name != ".derive.lock"
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


def _assert_command(record: dict[str, Any]) -> None:
    contracts = load_contract_set()
    contract = contracts.named("result/command")
    frozen = contract.versions[-1]
    found = violations(
        record, contracts.frozen_schema(contract, frozen), contracts.schema_registry()
    )
    assert not found, found
    _no_score(record)


def _no_score(value: object) -> None:
    if isinstance(value, dict):
        assert "score" not in value
        for child in value.values():
            _no_score(child)
    elif isinstance(value, list):
        for child in value:
            _no_score(child)
