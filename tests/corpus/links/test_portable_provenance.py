"""A development handoff binds the exporting contract set and refuses any other (spec section 17.7)."""

import io
import json
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.canonical import SEAL_FIELD, canonical_json, seal_of, sha256_bytes
from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.hosts.host_hashes import run_directory
from ss_track.corpus.links.interactive_state import save_checkpoint
from ss_track.corpus.links.portable import unpack_handoff
from ss_track.corpus.links.portable_accept import accept_handoff
from ss_track.corpus.links.portable_archive import (
    HASHES_MEMBER,
    LINKS_MEMBER,
    MANIFEST_MEMBER,
    build_archive,
    read_archive,
)
from ss_track.corpus.links.portable_provenance import exported_contract_set
from ss_track.corpus.links.portable_state import accepted_path
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.records.kinds import LINK_REVIEW_HANDOFF
from ss_track.corpus.storage.layout import discovery_run_directory
from tests.corpus.links._portable import (
    CORPUS,
    LINKS,
    REVIEWER,
    checkpoint_of,
    expiry,
    export,
    prepare,
    write_inputs,
)

DIGEST = "a" * 64
ALTERED = "0" * 64


def _archive(path: Path) -> Path:
    """Write a small archive whose records are placeholders: enough for the manifest checks."""
    payload, _ = build_archive(
        expires_on=expiry(),
        corpus_id=CORPUS,
        corpus_manifest_sha256=DIGEST,
        frame_set_sha256=DIGEST,
        links_run_id=LINKS,
        links_manifest_sha256=DIGEST,
        base_checkpoint_sha256=None,
        checkpoint_sha256=None,
        members={LINKS_MEMBER: b"{}", HASHES_MEMBER: b"{}"},
    )
    path.write_bytes(payload)
    return path


def _resealed(path: Path, edit: Callable[[dict[str, Any]], None]) -> Path:
    """Rewrite the manifest of an archive by hand, resealing it as a careful forger would."""
    stream = io.BytesIO()
    with (
        tarfile.open(path, mode="r:") as source,
        tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as target,
    ):
        for info in source:
            handle = source.extractfile(info)
            assert handle is not None
            payload = handle.read()
            if info.name == MANIFEST_MEMBER:
                manifest = json.loads(payload)
                edit(manifest)
                manifest[SEAL_FIELD] = seal_of(manifest)
                payload = canonical_json(manifest)
                info.size = len(payload)
            target.addfile(info, io.BytesIO(payload))
    path.write_bytes(stream.getvalue())
    return path


def _refusal(path: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        read_archive(path)
    return caught.value


def test_a_handoff_pins_every_installed_record_and_shared_contract(tmp_path: Path) -> None:
    manifest = read_archive(_archive(tmp_path / "handoff.tar")).manifest
    structures = contract_stamp.installed_fingerprints()
    meanings = contract_stamp.installed_meanings()
    assert structures is not None and meanings is not None
    assert manifest["contract_set"] == [
        {"contract": name, "structure": structures[name], "meaning": meanings[name]}
        for name in sorted(structures)
    ]
    assert {"record/link-review-handoff", "record/corpus-links", "shared/types"} <= set(structures)


def test_missing_pins_refuse_with_the_handoff_remedy(tmp_path: Path) -> None:
    absent = _resealed(_archive(tmp_path / "absent.tar"), lambda record: record.pop("contract_set"))
    nulled = _resealed(
        _archive(tmp_path / "null.tar"), lambda record: record.update(contract_set=None)
    )
    for path in (absent, nulled):
        refusal = _refusal(path)
        assert refusal.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
        assert refusal.details["field"] == "contract_set"
        assert "spec section 17.7" in str(refusal.details["remedy"])


@pytest.mark.parametrize(
    ("edit", "code"),
    [
        (lambda rows: rows[0].update(meaning=ALTERED), RefusalCode.RECORD_SCHEMA_UNSUPPORTED),
        (lambda rows: rows[-1].update(structure=ALTERED), RefusalCode.RECORD_SCHEMA_UNSUPPORTED),
        (lambda rows: rows.pop(), RefusalCode.RECORD_SCHEMA_UNSUPPORTED),
        (lambda rows: rows.reverse(), RefusalCode.RECORD_TAMPERED),
        (lambda rows: rows.append(rows[-1]), RefusalCode.RECORD_TAMPERED),
        (lambda rows: rows[0].pop("meaning"), RefusalCode.RECORD_TAMPERED),
        (lambda rows: rows.append("record/frame-set"), RefusalCode.RECORD_TAMPERED),
    ],
    ids=["meaning", "structure", "omitted", "unsorted", "repeated", "incomplete", "not-a-row"],
)
def test_changed_or_damaged_pins_refuse(
    tmp_path: Path, edit: Callable[[list[Any]], None], code: RefusalCode
) -> None:
    path = _resealed(
        _archive(tmp_path / "handoff.tar"), lambda record: edit(record["contract_set"])
    )
    refusal = _refusal(path)
    assert refusal.code is code
    if code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED:
        assert len(refusal.details["changed_contracts"]) == 1  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("installed", "contract"),
    [("installed_meanings", "record/corpus-links"), ("installed_fingerprints", "shared/types")],
)
def test_roots_with_equal_bytes_but_other_pins_refuse_before_any_local_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed: str, contract: str
) -> None:
    inputs, corpus_path = write_inputs(tmp_path / "inputs")
    origin, receiver = tmp_path / "origin", tmp_path / "receiver"
    prepare(origin, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    checkpoint_of(origin).parent.mkdir()
    save_checkpoint(checkpoint_of(origin), REVIEWER, {})
    archive = tmp_path / "handoff.tar"
    export(origin, archive, [*inputs, corpus_path], "origin-identity")

    original: dict[str, str] = getattr(contract_stamp, installed)()
    monkeypatch.setattr(contract_stamp, installed, lambda: original | {contract: ALTERED})
    prepare(receiver, inputs, corpus_path)  # stamped under the receiver's pins
    assert _frames(receiver) == _frames(origin)

    with pytest.raises(CorpusRefusal) as caught:
        accept_handoff(receiver, archive, "receiver-identity", "comparison", REVIEWER, True)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    assert caught.value.details["changed_contracts"] == [contract]
    assert not discovery_run_directory(receiver, LINKS).exists()
    assert not run_directory(receiver, "receiver-identity").exists()
    assert not run_directory(receiver, "comparison").exists()
    with pytest.raises(CorpusRefusal):
        unpack_handoff(archive, tmp_path / "recipes", True)
    assert not (tmp_path / "recipes").exists()


def test_matching_pins_round_trip_into_the_accepted_handoff(tmp_path: Path) -> None:
    inputs, corpus_path = write_inputs(tmp_path / "inputs")
    origin, receiver = tmp_path / "origin", tmp_path / "receiver"
    prepare(origin, inputs, corpus_path)
    prepare(receiver, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    archive = tmp_path / "handoff.tar"
    export(origin, archive, [*inputs, corpus_path], "origin-identity")

    accept_handoff(receiver, archive, "receiver-identity", "comparison", REVIEWER, True)
    accepted = read_sealed(accepted_path(receiver, LINKS), LINK_REVIEW_HANDOFF)
    assert accepted["contract_set"] == exported_contract_set()


def test_a_released_handoff_carries_no_pins_and_reads_by_major(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contract_stamp, "installed_fingerprints", lambda: None)
    monkeypatch.setattr(contract_stamp, "installed_meanings", lambda: None)
    inputs, corpus_path = write_inputs(tmp_path / "inputs")
    origin, receiver = tmp_path / "origin", tmp_path / "receiver"
    prepare(origin, inputs, corpus_path)
    prepare(receiver, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    archive = tmp_path / "handoff.tar"
    export(origin, archive, [*inputs, corpus_path], "origin-identity")
    assert read_archive(archive).manifest["contract_set"] is None

    result = accept_handoff(receiver, archive, "receiver-identity", "comparison", REVIEWER, True)
    assert result.status == "identical"
    assert not (receiver / contract_stamp.STAMP_NAME).exists()

    monkeypatch.undo()  # the same archive opened by a development install has no pins to prove
    with pytest.raises(CorpusRefusal) as caught:
        unpack_handoff(archive, tmp_path / "recipes", True)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def _frames(data_root: Path) -> list[str]:
    frames = sorted((data_root / "corpus" / CORPUS / "frames").rglob("*.rgb24"))
    return [sha256_bytes(path.read_bytes()) for path in frames]
