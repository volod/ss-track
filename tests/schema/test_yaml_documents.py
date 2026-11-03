"""Explicit declaration validation uses strict YAML, without changing corpus readers."""

from pathlib import Path

import pytest

from ss_track.refusal import CorpusRefusal, RefusalCode
from ss_track.schema import validate_file
from ss_track.schema._documents import _read_document
from tests.schema.conftest import Register, versioned_schema


def test_yaml_dates_are_normalized_only_for_validation(
    tmp_path: Path, contract_root: Path, register: Register
) -> None:
    schema = versioned_schema("declaration", "dated", "1.0.0")
    schema["properties"]["until"] = {"type": "string", "format": "date", "description": "A date."}
    register(schema)
    path = tmp_path / "declaration.yaml"
    text = "schema_version: 1\nuntil: 2026-11-02\n"
    path.write_text(text)
    result = validate_file(path, contract_name="declaration/dated", root=contract_root)
    assert result.contract == "declaration/dated" and not result.seal_checked
    assert path.read_text() == text


@pytest.mark.parametrize(
    "text",
    [
        "schema_version: 3\nschema_version: 3\n",
        "schema_version: 3\nnested: {a: 1, a: 2}\n",
        "value: .nan\n",
        "value: .inf\n",
        "value: -.inf\n",
        "value: 2026-11-02T12:00:00Z\n",
        "1: value\n",
        "value: !!binary YQ==\n",
        "value: &cycle [*cycle]\n",
    ],
)
def test_non_json_yaml_values_refuse_cleanly(tmp_path: Path, text: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(text)
    with pytest.raises(CorpusRefusal) as caught:
        validate_file(path, contract_name="declaration/corpus")
    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_yaml_corpus_and_json_corpus_follow_the_same_contract(tmp_path: Path) -> None:
    path = tmp_path / "corpus.yaml"
    path.write_text(
        "schema_version: 3\ncorpus_id: example\n"
        "scenario_rights: {sharing: restricted, max_sensitivity: high}\n"
        "groups:\n- group_id: one\n  split: development\n  encounters:\n"
        "  - encounter_id: encounter\n    streams:\n"
        f"    - stream_id: camera\n      source_sha256: {'a' * 64}\n"
    )
    assert validate_file(path, contract_name="declaration/corpus").version == "3.0.0"
    assert isinstance(_read_document(path, declaration=True), dict)
    path.write_text(path.read_text().replace("schema_version: 3", "schema_version: 3.0"))
    with pytest.raises(CorpusRefusal) as caught:
        validate_file(path, contract_name="declaration/corpus")
    assert caught.value.code is RefusalCode.MANIFEST_INVALID


@pytest.mark.parametrize("payload", ['{"value": 1e999}', '{"nested": [-1e999]}'])
def test_json_overflow_is_not_hidden_inside_open_details(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "overflow.json"
    path.write_text(payload)
    with pytest.raises(CorpusRefusal) as caught:
        validate_file(path, contract_name="result/command")
    assert caught.value.code is RefusalCode.RECORD_INVALID
    assert "non-finite" in caught.value.message


def test_real_recording_preserves_descriptions_numbers_and_dates(tmp_path: Path) -> None:
    path = tmp_path / "recording.yaml"
    text = (
        "schema_version: 2\nsource: {path: clip.mkv}\n"
        "rights: {holder: Owner, basis: owned, retention: project, retain_until: 2030-01-02, "
        "derived_frames: true, sharing: restricted}\n"
        "sensitivity: {level: low}\n"
        "capture: {camera: 42, exposure: automatic, "
        "range: {status: estimated, value_m: 'about 3', method: visual}}\n"
    )
    path.write_text(text)
    assert validate_file(path, contract_name="declaration/recording").version == "2.0.0"
    assert path.read_text() == text
    path.write_text(text.replace("camera: 42", "camera: null"))
    with pytest.raises(CorpusRefusal) as caught:
        validate_file(path, contract_name="declaration/recording")
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
