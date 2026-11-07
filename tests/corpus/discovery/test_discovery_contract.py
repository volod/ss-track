"""The discovery contracts refuse a record that misses identity, rights or provenance.

A writer defect is `RECORD_INVALID` with nothing sealed. These are the refusals JSON Schema itself
states, so a consumer holding only `contracts/` refuses them too.
"""

from typing import Any

import pytest

from tests.corpus.discovery._damage import (
    Damage,
    audit,
    drop,
    extractor,
    refused,
    selection,
    set_to,
    sibling,
)
from tests.corpus.discovery._records import synthetic_bodies, written_form
from tests.schema.conftest import EXAMPLES


def test_the_golden_records_seal_and_match_their_examples() -> None:
    records = synthetic_bodies().seal()
    examples = {
        "record-discovery-run.json": records.run,
        "record-candidate-inventory.json": records.inventories["one"],
    }

    for name, record in examples.items():
        assert (EXAMPLES / name).read_text(encoding="ascii") == written_form(record)


def test_the_run_seals_each_inventory_it_lists() -> None:
    records = synthetic_bodies().seal()
    lines: Any = records.run["inventories"]

    assert [line["stream_id"] for line in lines] == ["one", "two"]
    assert [line["inventory_sha256"] for line in lines] == [
        records.inventories[name]["manifest_sha256"] for name in ("one", "two")
    ]


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(drop("inventory.source_manifest_sha256"), id="no-rights-reference"),
        pytest.param(drop("run.frame_set_sha256"), id="no-frame-set"),
        pytest.param(drop("inventory.bundle_sha256"), id="no-bundle"),
        pytest.param(drop("inventory.candidates.3.window"), id="sibling-time-alone"),
        pytest.param(
            set_to(sibling, frame_index=13), id="sibling-names-a-frame-outside-the-contract"
        ),
        pytest.param(
            set_to(lambda b: sibling(b)["origin"], seconds=0.6), id="sibling-time-in-seconds"
        ),
        pytest.param(drop("inventory.candidates.3.origin.slot"), id="sibling-without-slot"),
        pytest.param(drop("run.hint_sources.0.ffmpeg_version"), id="hint-without-ffmpeg"),
        pytest.param(drop("run.hint_sources.0.sample_rate"), id="hint-without-rate"),
        pytest.param(drop("run.extractors.0.package.commit"), id="no-package-commit"),
        pytest.param(drop("run.extractors.0.weights.0.sha256"), id="no-weight-hash"),
        pytest.param(drop("run.extractors.0.weights.0.revision"), id="no-weight-revision"),
        pytest.param(set_to(extractor, weights=[]), id="no-weights"),
        pytest.param(set_to(extractor, libraries=[]), id="no-libraries"),
        pytest.param(drop("run.extractors.0.batch_size"), id="no-batch-size"),
        pytest.param(drop("run.extractors.0.dtype"), id="no-dtype"),
        pytest.param(drop("run.extractors.0.preprocessing"), id="no-preprocessing"),
        pytest.param(set_to(extractor, device="auto"), id="device-not-named"),
        pytest.param(
            set_to(lambda b: extractor(b)["package"], commit="12cb086"), id="short-commit"
        ),
    ],
)
def test_the_contract_refuses_a_record_missing_identity_or_provenance(damage: Damage) -> None:
    refusal = refused(damage)

    assert "breaks urn:ss-track:contract:record:" in refusal.message


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(selection("one", "pool-001", probability=1.5), id="above-one"),
        pytest.param(selection("one", "pool-002", probability=-0.1), id="below-zero"),
        pytest.param(selection("one", "pool-001", probability=0.0), id="selected-at-zero"),
        pytest.param(selection("one", "pool-002", probability=1.0), id="unselected-at-one"),
        pytest.param(audit("one", "pool-000", inclusion_probability=0.0), id="audit-at-zero"),
        pytest.param(audit("one", "pool-002", inclusion_probability=1.0), id="unsampled-certain"),
        pytest.param(selection("one", "pool-001", probability=float("nan")), id="not-a-number"),
        pytest.param(selection("one", "pool-001", rank=0), id="rank-zero"),
    ],
)
def test_the_contract_refuses_an_impossible_probability(damage: Damage) -> None:
    refused(damage)
