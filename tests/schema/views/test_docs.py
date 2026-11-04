"""Contract reference output covers frozen fields and annotated lineage."""

from pathlib import Path

from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.views.docs import fields, render_docs


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
