"""A blinded audit packet hides selection and source cues and maps decisions back."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.discovery.run import run_discovery
from ss_track.corpus.evaluation.inputs import read_evidence
from ss_track.corpus.evaluation.report import claim
from ss_track.corpus.records.kinds import AUDIT_BLINDING, CORPUS_FREEZE
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal
from ss_track.corpus.review.blind import present_audit, unblind_audit
from ss_track.corpus.review.blind_key import read_blinding
from ss_track.corpus.review.blind_review import read_audit_review
from ss_track.corpus.review.decisions import read_review
from ss_track.corpus.review.freeze import freeze_corpus
from ss_track.corpus.storage.layout import blinding_path, freeze_path
from tests.corpus.conftest import last_record
from tests.corpus.review._review import (
    PLAN,
    RUN_ID,
    STOCK_DECISIONS,
    review_links,
    staged,
    write_review,
)

_AUDIT = "audit-1"
_TOKEN = re.compile(r"[A-Za-z0-9_.-]+")
_CUES = {
    "selected",
    "not_selected",
    "audit_sample",
    "sibling",
    "probability",
    "uniform",
    "ssl-diverse",
    "rank",
    "score",
    "one",
    "two",
    "three",
    "site-a",
    "site-b",
    "enc-one",
    "enc-two",
    "enc-three",
    "pool-000",
    "pool-001",
    "pool-002",
}


def _run(media: Path, data_root: Path, run_id: str, **audit: int) -> None:
    plan = dict(PLAN)
    plan["run_id"] = run_id
    plan["audit"] = {"seed": audit.get("seed", 7), "sample_size": audit.get("sample_size", 3)}
    plan["selection"] = {"method": "uniform", "budget": 2, "seed": audit.get("selection_seed", 9)}
    path = media / f"{run_id}.yaml"
    path.write_text(yaml.safe_dump(plan), encoding="ascii")
    run_discovery(path, data_root)


def _identity(items: Any) -> list[tuple[Any, Any, Any]]:
    return [(item["item_id"], item["stream_id"], item["candidate_id"]) for item in items]


def _surface(packet: Path) -> str:
    names = [str(path.relative_to(packet)) for path in packet.rglob("*") if path.is_file()]
    return (packet / "review.yaml").read_text(encoding="ascii") + "\n" + "\n".join(names)


def _complete(packet: Path) -> None:
    document = yaml.safe_load((packet / "review.yaml").read_text(encoding="ascii"))
    document["reviewer"] = "site lead"
    document["reviewer_minutes"] = 12
    document["independence"] = "declared"
    document["blinding"] = "not_declared"
    first, second, *rest = document["observations"]
    document["observations"] = [
        {"item_id": first["item_id"], "decision": "include", "observation": "unknown"},
        {
            "item_id": second["item_id"],
            "decision": "exclude",
            "observation": "unknown",
            "reason": "other",
            "note": "not useful",
        },
        *rest,
    ]
    (packet / "review.yaml").write_text(yaml.safe_dump(document), encoding="ascii")


def test_the_packet_names_no_source_and_the_mapping_does(
    pool: Any, cli_root: Path, media: Path, data_root: Path, caplog: Any
) -> None:
    packet = media / "packet"
    code = main(
        ["discover", "blind", "--audit-id", _AUDIT, "--run-id", RUN_ID, "--out", str(packet)]
    )

    record = last_record(caplog)
    blind = record["blind"]
    assert code == 0 and record["status"] == "presented"
    assert blind == {
        "audit_id": _AUDIT,
        "presented": 6,
        "withheld": 3,
        "outside_sample": 0,
        "run_count": 1,
        "unselected": 4,
    }
    tokens = set(_TOKEN.findall(_surface(packet)))
    hashes = [pool[0].source_sha256, pool[1].source_sha256, pool[2].source_sha256]
    assert tokens.isdisjoint(_CUES) and all(digest not in _surface(packet) for digest in hashes)
    assert "locked_without_policy" in (packet / "review.yaml").read_text(encoding="ascii")
    pictures = sorted(packet.glob("items/*/*.png"))
    assert pictures and all(re.fullmatch(r"\d{3,}\.png", path.name) for path in pictures)
    private = read_sealed(blinding_path(data_root, _AUDIT), AUDIT_BLINDING)
    assert private["withheld"] == [
        {"stream_id": "three", "reason": "locked_without_policy", "count": 3}
    ]
    assert "three" not in _surface(packet)
    with pytest.raises(CorpusRefusal):
        read_audit_review(packet / "review.yaml")
    again = main(
        ["discover", "blind", "--audit-id", _AUDIT, "--run-id", RUN_ID, "--out", str(packet)]
    )
    assert again == 0 and last_record(caplog)["status"] == "unchanged"
    edited = (packet / "review.yaml").read_bytes() + b"# note\n"
    (packet / "review.yaml").write_bytes(edited)
    with pytest.raises(CorpusRefusal) as conflict:
        present_audit(_AUDIT, [RUN_ID], packet, data_root)
    assert conflict.value.code is RefusalCode.CORPUS_CONFLICT
    assert (packet / "review.yaml").read_bytes() == edited


def test_matched_runs_share_items_and_a_different_sample_writes_nothing(
    pool: Any, data_root: Path, media: Path
) -> None:
    del pool
    _run(media, data_root, "discovery-2")
    _run(media, data_root, "discovery-thin", sample_size=1)
    shared = media / "shared"
    present_audit("audit-shared", [RUN_ID, "discovery-2"], shared, data_root)
    alone = media / "alone"
    present_audit("audit-alone", [RUN_ID], alone, data_root)
    thin = media / "thin"
    present_audit("audit-thin", ["discovery-thin"], thin, data_root)

    shared_key = read_sealed(blinding_path(data_root, "audit-shared"), AUDIT_BLINDING)
    alone_key = read_sealed(blinding_path(data_root, "audit-alone"), AUDIT_BLINDING)
    thin_key = read_sealed(blinding_path(data_root, "audit-thin"), AUDIT_BLINDING)
    assert _identity(shared_key["items"]) == _identity(alone_key["items"])
    assert {item["item_id"] for item in shared_key["items"]} == {
        path.parent.name for path in shared.glob("items/*/*.png")
    }
    assert (
        thin_key["outside_sample"],
        len(thin_key["items"]),
        thin_key["withheld"][0]["count"],
    ) == (
        6,
        2,
        1,
    )
    refused = media / "refused"
    with pytest.raises(CorpusRefusal) as caught:
        present_audit("audit-mixed", [RUN_ID, "discovery-thin"], refused, data_root)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert not refused.exists() and not blinding_path(data_root, "audit-mixed").exists()


def test_unblinding_restores_candidates_and_an_unknown_observation(
    pool: Any, data_root: Path, media: Path
) -> None:
    del pool
    packet = media / "packet"
    present_audit(_AUDIT, [RUN_ID], packet, data_root)
    _complete(packet)
    mapped = media / "mapped"
    result = unblind_audit(_AUDIT, packet / "review.yaml", mapped, data_root)

    review = read_review(mapped / f"{RUN_ID}.yaml")
    private = read_sealed(blinding_path(data_root, _AUDIT), AUDIT_BLINDING)
    included = next(item for item in private["items"] if item["item_id"] == "item-000")
    decision = review.decisions[(included["stream_id"], included["candidate_id"])]
    assert result.to_record()["status"] == "unblinded"
    assert decision.decision == "include" and decision.observation == "unknown"
    assert (review.independence, review.blinding, review.reviewer_minutes, review.audit_id) == (
        "declared",
        "not_declared",
        12,
        _AUDIT,
    )
    assert result.to_record()["blind"]["independence"] == "declared"
    loose = media / "loose"
    loose.mkdir()
    (loose / "review.yaml").write_bytes((packet / "review.yaml").read_bytes())
    again = unblind_audit(_AUDIT, loose / "review.yaml", media / "mapped-loose", data_root)
    assert again.to_record()["status"] == "unblinded"


def test_forged_mappings_and_mismatched_reviews_are_refused(
    pool: Any, data_root: Path, media: Path
) -> None:
    del pool
    packet = media / "packet"
    present_audit(_AUDIT, [RUN_ID], packet, data_root)
    _complete(packet)
    path = blinding_path(data_root, _AUDIT)
    original = path.read_bytes()
    path.chmod(0o644)
    path.write_bytes(original.replace(b"item-000", b"item-999", 1))
    with pytest.raises(CorpusRefusal) as tampered:
        unblind_audit(_AUDIT, packet / "review.yaml", media / "bad", data_root)
    assert tampered.value.code is RefusalCode.RECORD_TAMPERED

    record = json.loads(original)
    record["items"][0]["candidate_id"] = "not-a-candidate"
    record.pop("manifest_sha256")
    path.write_text(json.dumps(seal(record), indent=2) + "\n", encoding="ascii")
    with pytest.raises(CorpusRefusal) as mismatched:
        unblind_audit(_AUDIT, packet / "review.yaml", media / "bad", data_root)
    assert mismatched.value.code is RefusalCode.RECORD_INVALID
    path.write_bytes(original)

    picture = next(packet.glob("items/item-000/*.png"))
    picture.chmod(0o644)
    picture.write_bytes(picture.read_bytes() + b"\0")
    with pytest.raises(CorpusRefusal) as frames:
        unblind_audit(_AUDIT, packet / "review.yaml", media / "bad", data_root)
    assert frames.value.code is RefusalCode.RECORD_INVALID

    document = yaml.safe_load((packet / "review.yaml").read_text(encoding="ascii"))
    document["observations"].append({"item_id": "item-999", "decision": "unreviewed"})
    extra = media / "extra.yaml"
    extra.write_text(yaml.safe_dump(document), encoding="ascii")
    with pytest.raises(CorpusRefusal) as unexpected:
        unblind_audit(_AUDIT, extra, media / "bad", data_root)
    assert unexpected.value.code is RefusalCode.MANIFEST_INVALID
    document["audit_id"] = "audit-other"
    document["observations"].pop()
    extra.write_text(yaml.safe_dump(document), encoding="ascii")
    with pytest.raises(CorpusRefusal) as other:
        unblind_audit(_AUDIT, extra, media / "bad", data_root)
    assert other.value.code is RefusalCode.MANIFEST_INVALID
    with pytest.raises(CorpusRefusal) as missing:
        read_blinding(data_root, "audit-missing")
    assert missing.value.code is RefusalCode.RECORD_TAMPERED
    duplicated = yaml.safe_load((packet / "review.yaml").read_text(encoding="ascii"))
    duplicated["observations"].insert(0, duplicated["observations"][0])
    duplicate = media / "duplicate.yaml"
    duplicate.write_text(yaml.safe_dump(duplicated), encoding="ascii")
    with pytest.raises(CorpusRefusal) as twice:
        unblind_audit(_AUDIT, duplicate, media / "bad", data_root)
    assert twice.value.code is RefusalCode.MANIFEST_INVALID
    named = yaml.safe_load((packet / "review.yaml").read_text(encoding="ascii"))
    named["observations"][0]["stream_id"] = "one"
    leaked = media / "leaked.yaml"
    leaked.write_text(yaml.safe_dump(named), encoding="ascii")
    with pytest.raises(CorpusRefusal) as identity:
        unblind_audit(_AUDIT, leaked, media / "bad", data_root)
    assert identity.value.code is RefusalCode.MANIFEST_INVALID
    with pytest.raises(CorpusRefusal) as occupied:
        present_audit(RUN_ID, [RUN_ID], media / "occupied", data_root)
    assert occupied.value.code is RefusalCode.CORPUS_CONFLICT
    with pytest.raises(CorpusRefusal) as inside:
        present_audit(
            "audit-inside", [RUN_ID], blinding_path(data_root, "audit-inside").parent, data_root
        )
    assert inside.value.code is RefusalCode.STORAGE_FAILED


def test_declared_provenance_is_frozen_and_claims_are_not_verification(
    pool: Any, data_root: Path, media: Path
) -> None:
    del pool
    review = staged(media, data_root, corpus_id="frozen-blind")
    document = yaml.safe_load(review.read_text(encoding="ascii"))
    document |= {
        "independence": "declared",
        "blinding": "not_declared",
        "reviewer_minutes": 12,
        "audit_id": _AUDIT,
    }
    review.write_text(yaml.safe_dump(document), encoding="ascii")
    review_links(data_root, "frozen-blind", "links-blind")
    freeze_corpus("frozen-blind", review, "links-blind", data_root)

    record = read_sealed(freeze_path(data_root, "frozen-blind"), CORPUS_FREEZE)
    assert record["review"]["independence"] == "declared"
    assert record["review"]["audit_id"] == _AUDIT
    assert record["review"]["reviewer_minutes"] == 12
    plain = read_review(write_review(media / "plain.yaml", *STOCK_DECISIONS))
    assert (plain.independence, plain.blinding, plain.reviewer_minutes, plain.audit_id) == (
        None,
        None,
        None,
        None,
    )
    evidence = read_evidence(data_root, RUN_ID, None, "frozen-blind")
    assert (evidence.independence, evidence.blinding, evidence.reviewer_minutes) == (
        "declared",
        "not_declared",
        12,
    )
    assert claim(None, None) == "unrecorded"
    assert claim("declared", "declared") == "declared"
    assert claim("declared", "not_declared") == "mixed"
