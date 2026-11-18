"""Portable review compares independently created corpora before moving decisions."""

import io
import tarfile
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.links.decisions import Decision
from ss_track.corpus.links.interactive_state import read_checkpoint, save_checkpoint
from ss_track.corpus.links.portable import export_handoff, unpack_handoff
from ss_track.corpus.links.portable_accept import accept_handoff
from ss_track.corpus.links.records import read_links
from ss_track.corpus.links.run import LinkRequest, write_links
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


def test_interrupted_review_round_trips_between_independent_data_roots(tmp_path: Path) -> None:
    inputs, corpus_path = write_inputs(tmp_path / "inputs")
    origin, reviewer = tmp_path / "origin", tmp_path / "reviewer"
    pair = prepare(origin, inputs, corpus_path)
    prepare(reviewer, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    links: Any = read_links(origin, LINKS)
    checkpoint_of(origin).parent.mkdir()
    save_checkpoint(checkpoint_of(origin), REVIEWER, {})
    outgoing = tmp_path / "outgoing.tar"
    recipes = [*inputs, corpus_path]
    export(origin, outgoing, recipes, "origin-identity")

    unpacked = tmp_path / "unpacked"
    result = unpack_handoff(outgoing, unpacked, True)
    assert result.details["recipe_count"] == 3
    assert sorted(path.name for path in unpacked.iterdir()) == sorted(path.name for path in recipes)
    accepted = accept_handoff(
        reviewer, outgoing, "reviewer-identity", "reviewer-comparison", REVIEWER, True
    )
    assert accepted.status == "identical"
    assert read_links(reviewer, LINKS)["manifest_sha256"] == links["manifest_sha256"]
    assert read_checkpoint(checkpoint_of(reviewer), REVIEWER, links["links"]) == {}

    decision = Decision(tuple(sorted(pair)), "unrelated", "independent sessions")
    save_checkpoint(checkpoint_of(reviewer), REVIEWER, {decision.sources: decision})
    returned = tmp_path / "returned.tar"
    export(reviewer, returned, recipes, "reviewer-return-identity")
    accept_handoff(origin, returned, "origin-return-identity", "origin-comparison", REVIEWER, True)
    restored = read_checkpoint(checkpoint_of(origin), REVIEWER, links["links"])
    assert restored[decision.sources].decision == "unrelated"
    reviewed = write_links(
        LinkRequest("portable-reviewed", CORPUS, decisions_path=checkpoint_of(origin)), origin
    )
    assert reviewed.record["status"] == "clear"


def test_divergent_return_never_changes_existing_decisions(tmp_path: Path) -> None:
    inputs, corpus_path = write_inputs(tmp_path / "inputs")
    origin, reviewer = tmp_path / "origin", tmp_path / "reviewer"
    pair = prepare(origin, inputs, corpus_path)
    prepare(reviewer, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    checkpoint_of(origin).parent.mkdir()
    save_checkpoint(checkpoint_of(origin), REVIEWER, {})
    outgoing = tmp_path / "outgoing.tar"
    recipes = [*inputs, corpus_path]
    export(origin, outgoing, recipes, "origin-identity")
    accept_handoff(reviewer, outgoing, "reviewer-identity", "reviewer-comparison", REVIEWER, True)

    reviewer_decision = Decision(tuple(sorted(pair)), "unrelated", None)
    save_checkpoint(
        checkpoint_of(reviewer), REVIEWER, {reviewer_decision.sources: reviewer_decision}
    )
    returned = tmp_path / "returned.tar"
    export(reviewer, returned, recipes, "reviewer-return-identity")
    local_decision = Decision(tuple(sorted(pair)), "related", "local evidence")
    save_checkpoint(checkpoint_of(origin), REVIEWER, {local_decision.sources: local_decision})
    before = checkpoint_of(origin).read_bytes()

    with pytest.raises(CorpusRefusal) as caught:
        accept_handoff(
            origin, returned, "origin-return-identity", "origin-comparison", REVIEWER, True
        )
    assert caught.value.code is RefusalCode.IMPORT_CONFLICT
    assert checkpoint_of(origin).read_bytes() == before


def test_unauthorized_expired_and_corrupt_archives_are_refused(tmp_path: Path) -> None:
    inputs, corpus_path = write_inputs(tmp_path / "inputs")
    origin, reviewer = tmp_path / "origin", tmp_path / "reviewer"
    prepare(origin, inputs, corpus_path)
    prepare(reviewer, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    archive = tmp_path / "handoff.tar"
    export(origin, archive, [*inputs, corpus_path], "origin-identity")

    with pytest.raises(CorpusRefusal) as caught:
        accept_handoff(reviewer, archive, "local-identity", "comparison", REVIEWER, False)
    assert caught.value.code is RefusalCode.RIGHTS_CONFLICT
    assert not discovery_run_directory(reviewer, LINKS).exists()

    expired = tmp_path / "expired.tar"
    export_handoff(
        origin,
        LINKS,
        CORPUS,
        "expired-identity",
        expiry(-1),
        expired,
        [*inputs, corpus_path],
        REVIEWER,
    )
    with pytest.raises(CorpusRefusal) as caught:
        unpack_handoff(expired, tmp_path / "expired-output", True)
    assert caught.value.code is RefusalCode.RETENTION_EXPIRED

    corrupt = tmp_path / "corrupt.tar"
    damaged = bytearray(archive.read_bytes())
    damaged[600] ^= 1
    corrupt.write_bytes(damaged)
    with pytest.raises(CorpusRefusal) as caught:
        unpack_handoff(corrupt, tmp_path / "corrupt-output", True)
    assert caught.value.code is RefusalCode.RECORD_TAMPERED

    omitted = tmp_path / "omitted.tar"
    stream = io.BytesIO()
    with (
        tarfile.open(archive, mode="r:") as source,
        tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as target,
    ):
        for info in source:
            if info.name != "records/links.json":
                target.addfile(info, source.extractfile(info))
    omitted.write_bytes(stream.getvalue())
    with pytest.raises(CorpusRefusal) as caught:
        unpack_handoff(omitted, tmp_path / "omitted-output", True)
    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_different_local_dataset_is_refused_before_review_state_changes(tmp_path: Path) -> None:
    inputs, corpus_path = write_inputs(tmp_path / "inputs")
    origin, other = tmp_path / "origin", tmp_path / "other"
    prepare(origin, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    archive = tmp_path / "handoff.tar"
    export(origin, archive, [*inputs, corpus_path], "origin-identity")
    prepare(other, inputs, corpus_path)
    frame = next((other / "corpus" / CORPUS / "frames").rglob("*.rgb24"))
    frame.chmod(0o644)
    frame.write_bytes(b"changed")

    with pytest.raises(CorpusRefusal) as caught:
        accept_handoff(other, archive, "other-identity", "comparison", REVIEWER, True)
    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert not discovery_run_directory(other, LINKS).exists()
