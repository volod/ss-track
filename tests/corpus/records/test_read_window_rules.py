"""The rules a view and a projection keep, each shown on the smallest record that breaks one."""

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from ss_track.core.refusal import JsonValue
from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus, stage_corpus
from ss_track.corpus.records.read_window import View, apply_views, check_view, view_findings
from ss_track.corpus.records.sealed import read_comparable
from ss_track.corpus.versions.builder import CORPUS_MANIFEST
from tests.corpus._shared_frames import V0, V1, V2, check_of, not_compared
from tests.corpus.conftest import WriteCorpus, reseal, self_sealed, single_group, stream_of

_KIND = "test-record"
_RECORD: dict[str, JsonValue] = {"kind": _KIND, "schema_version": 1, "name": "a"}


def _same(record: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return dict(record)


@pytest.mark.parametrize("pointer", ["/schema_version", "/kind", "/manifest_sha256", ""])
def test_a_view_cannot_stamp_a_major_rename_a_kind_or_touch_the_seal(pointer: str) -> None:
    assert view_findings(View(_KIND, 1, (pointer,), _same))


@pytest.mark.parametrize(
    "pointer",
    [
        "/generated_cases/*/transform_revision",
        "/streams/*/rights/retain_until",
        "/decode_policy/revision",
        "/streams/*/split",
    ],
)
def test_a_view_never_derives_a_judgment_or_an_algorithm_revision(pointer: str) -> None:
    assert view_findings(View(_KIND, 1, (pointer,), _same))


def test_a_view_that_changes_the_record_it_read_is_named() -> None:
    def mutates(record: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        record["name"] = "b"  # type: ignore[index]
        return dict(record)

    findings = check_view(View(_KIND, 1, ("/name",), mutates), dict(_RECORD))

    assert "the view changed the record it read" in findings


def test_a_declared_view_with_no_function_is_a_damaged_installation() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        apply_views(self_sealed(_RECORD), {}, 1, 2)

    assert caught.value.code is RefusalCode.CONTRACT_SET_INVALID


def test_a_record_lacking_a_fact_its_projection_reads_is_tampered(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    built = build_corpus(write_corpus([stream_of(imported)]), data_root)
    record = json.loads(built.manifest_path.read_text(encoding="ascii"))
    stream = {key: value for key, value in record["streams"][0].items() if key != "split"}
    reseal(built.manifest_path, streams=[stream])

    with pytest.raises(CorpusRefusal) as caught:
        read_comparable(built.manifest_path, CORPUS_MANIFEST)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_an_unprojected_version_ends_the_chain_behind_it(
    imported: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(imported, stream_id="a"))]
    build_corpus(write_grouped_corpus(groups, corpus_id=V0), data_root)
    v1 = build_corpus(write_grouped_corpus(groups, corpus_id=V1, supersedes=V0), data_root)
    stage_corpus(V1, data_root)
    reseal(v1.manifest_path, schema_version=CORPUS_MANIFEST.major + 1)
    moved = [single_group("held-out", "locked", stream_of(imported, stream_id="a"))]
    v2 = build_corpus(write_grouped_corpus(moved, corpus_id=V2, supersedes=V1), data_root)

    staged = stage_corpus(V2, data_root)

    lineage = v2.to_record()["lineage"]
    assert isinstance(lineage, dict)
    assert lineage["compared_versions"] == []
    assert check_of(staged)["compared_versions"] == []
    assert not_compared(staged) == [(V1, "other_schema", [])]
