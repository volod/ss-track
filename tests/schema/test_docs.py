"""Contract reference output covers frozen fields and annotated lineage."""

from pathlib import Path

from ss_track.schema.docs import fields, render_docs
from ss_track.schema.store import load_contract_set


def test_reference_output_is_complete_and_deterministic(tmp_path: Path) -> None:
    out = tmp_path / "reference"
    render_docs(out)
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*.md")}
    render_docs(out)
    assert before == {p.relative_to(out): p.read_bytes() for p in out.rglob("*.md")}
    contracts = load_contract_set()
    for contract in contracts.contracts:
        page = (out / contract.family / f"{contract.contract_id}.md").read_text()
        for version in contract.versions:
            for path, node in fields(contracts.frozen_schema(contract, version)):
                assert path in page
                for value in node.get("enum", []):
                    assert str(value) in page


def test_annotation_target_must_exist() -> None:
    from ss_track.schema.check import _annotation_resolves

    contracts = load_contract_set()
    assert _annotation_resolves(contracts, "record/frame-bundle#/properties/stream_id")
    assert not _annotation_resolves(contracts, "record/frame-bundle#/properties/missing")
    assert not _annotation_resolves(contracts, "record/missing#/properties/id")
