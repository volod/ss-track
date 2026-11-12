"""Portable review compares independently created corpora before moving decisions."""

import io
import tarfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import build_corpus, import_source, stage_corpus
from ss_track.corpus.links.decisions import Decision
from ss_track.corpus.links.interactive_state import read_checkpoint, save_checkpoint
from ss_track.corpus.links.portable import export_handoff, unpack_handoff
from ss_track.corpus.links.portable_accept import accept_handoff
from ss_track.corpus.links.records import read_links
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.storage.layout import discovery_run_directory
from tests.corpus._media import WIDTH, write_clip
from tests.corpus.conftest import corpus_declaration, encounter_of, group_of, recording_declaration

CORPUS = "portable-v1"
LINKS = "portable-links"
REVIEWER = "Reviewer"


def _write_inputs(root: Path) -> tuple[list[Path], Path]:
    root.mkdir()
    declarations = []
    for name, extra in (("one.mkv", 2), ("two.mkv", 4)):
        write_clip(root / name, width=WIDTH + extra)
        declaration = root / f"{name}.yaml"
        declaration.write_text(yaml.safe_dump(recording_declaration(name)), encoding="ascii")
        declarations.append(declaration)
    return declarations, root / "corpus.yaml"


def _prepare(data_root: Path, declarations: list[Path], corpus_path: Path) -> tuple[str, str]:
    first, second = [import_source(path, data_root) for path in declarations]
    groups = [
        group_of(
            "first-group",
            "development",
            encounter_of(
                "first-encounter",
                {"stream_id": "first", "source_sha256": first.source_sha256},
            ),
        ),
        group_of(
            "second-group",
            "development",
            encounter_of(
                "second-encounter",
                {"stream_id": "second", "source_sha256": second.source_sha256},
            ),
        ),
    ]
    corpus_path.write_text(
        yaml.safe_dump(corpus_declaration(groups, corpus_id=CORPUS)), encoding="ascii"
    )
    build_corpus(corpus_path, data_root)
    stage_corpus(CORPUS, data_root)
    return first.source_sha256, second.source_sha256


def _expiry(days: int = 7) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _checkpoint(data_root: Path) -> Path:
    return discovery_run_directory(data_root, LINKS) / "link-review" / "decisions.yaml"


def _export(data_root: Path, archive: Path, recipes: list[Path], identity: str) -> None:
    export_handoff(
        data_root,
        LINKS,
        CORPUS,
        identity,
        _expiry(),
        archive,
        recipes,
        REVIEWER,
    )


def test_interrupted_review_round_trips_between_independent_data_roots(tmp_path: Path) -> None:
    inputs, corpus_path = _write_inputs(tmp_path / "inputs")
    origin, reviewer = tmp_path / "origin", tmp_path / "reviewer"
    pair = _prepare(origin, inputs, corpus_path)
    _prepare(reviewer, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    links: Any = read_links(origin, LINKS)
    _checkpoint(origin).parent.mkdir()
    save_checkpoint(_checkpoint(origin), REVIEWER, {})
    outgoing = tmp_path / "outgoing.tar"
    recipes = [*inputs, corpus_path]
    _export(origin, outgoing, recipes, "origin-identity")

    unpacked = tmp_path / "unpacked"
    result = unpack_handoff(outgoing, unpacked, True)
    assert result.details["recipe_count"] == 3
    assert sorted(path.name for path in unpacked.iterdir()) == sorted(path.name for path in recipes)
    accepted = accept_handoff(
        reviewer, outgoing, "reviewer-identity", "reviewer-comparison", REVIEWER, True
    )
    assert accepted.status == "identical"
    assert read_links(reviewer, LINKS)["manifest_sha256"] == links["manifest_sha256"]
    assert read_checkpoint(_checkpoint(reviewer), REVIEWER, links["links"]) == {}

    decision = Decision(tuple(sorted(pair)), "unrelated", "independent sessions")
    save_checkpoint(_checkpoint(reviewer), REVIEWER, {decision.sources: decision})
    returned = tmp_path / "returned.tar"
    _export(reviewer, returned, recipes, "reviewer-return-identity")
    accept_handoff(origin, returned, "origin-return-identity", "origin-comparison", REVIEWER, True)
    restored = read_checkpoint(_checkpoint(origin), REVIEWER, links["links"])
    assert restored[decision.sources].decision == "unrelated"
    reviewed = write_links(
        LinkRequest("portable-reviewed", CORPUS, decisions_path=_checkpoint(origin)), origin
    )
    assert reviewed.record["status"] == "clear"


def test_divergent_return_never_changes_existing_decisions(tmp_path: Path) -> None:
    inputs, corpus_path = _write_inputs(tmp_path / "inputs")
    origin, reviewer = tmp_path / "origin", tmp_path / "reviewer"
    pair = _prepare(origin, inputs, corpus_path)
    _prepare(reviewer, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    _checkpoint(origin).parent.mkdir()
    save_checkpoint(_checkpoint(origin), REVIEWER, {})
    outgoing = tmp_path / "outgoing.tar"
    recipes = [*inputs, corpus_path]
    _export(origin, outgoing, recipes, "origin-identity")
    accept_handoff(reviewer, outgoing, "reviewer-identity", "reviewer-comparison", REVIEWER, True)

    reviewer_decision = Decision(tuple(sorted(pair)), "unrelated", None)
    save_checkpoint(_checkpoint(reviewer), REVIEWER, {reviewer_decision.sources: reviewer_decision})
    returned = tmp_path / "returned.tar"
    _export(reviewer, returned, recipes, "reviewer-return-identity")
    local_decision = Decision(tuple(sorted(pair)), "related", "local evidence")
    save_checkpoint(_checkpoint(origin), REVIEWER, {local_decision.sources: local_decision})
    before = _checkpoint(origin).read_bytes()

    with pytest.raises(CorpusRefusal) as caught:
        accept_handoff(
            origin, returned, "origin-return-identity", "origin-comparison", REVIEWER, True
        )
    assert caught.value.code is RefusalCode.IMPORT_CONFLICT
    assert _checkpoint(origin).read_bytes() == before


def test_unauthorized_expired_and_corrupt_archives_are_refused(tmp_path: Path) -> None:
    inputs, corpus_path = _write_inputs(tmp_path / "inputs")
    origin, reviewer = tmp_path / "origin", tmp_path / "reviewer"
    _prepare(origin, inputs, corpus_path)
    _prepare(reviewer, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    archive = tmp_path / "handoff.tar"
    _export(origin, archive, [*inputs, corpus_path], "origin-identity")

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
        _expiry(-1),
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
    inputs, corpus_path = _write_inputs(tmp_path / "inputs")
    origin, other = tmp_path / "origin", tmp_path / "other"
    _prepare(origin, inputs, corpus_path)
    write_links(LinkRequest(LINKS, CORPUS), origin)
    archive = tmp_path / "handoff.tar"
    _export(origin, archive, [*inputs, corpus_path], "origin-identity")
    _prepare(other, inputs, corpus_path)
    frame = next((other / "corpus" / CORPUS / "frames").rglob("*.rgb24"))
    frame.chmod(0o644)
    frame.write_bytes(b"changed")

    with pytest.raises(CorpusRefusal) as caught:
        accept_handoff(other, archive, "other-identity", "comparison", REVIEWER, True)
    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert not discovery_run_directory(other, LINKS).exists()
