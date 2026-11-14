"""Offline source inventory fixtures, including unresolved and hostile metadata."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.core.refusal import CorpusRefusal
from ss_track.corpus.sources.inventory import inventory_sources, read_inventory
from ss_track.schema.validation.enforce import read_declaration


def _video(path: str, **changes: Any) -> dict[str, Any]:
    return {
        "path": path,
        "source_reference": None,
        "annotation_reference": None,
        "upstream_split": None,
        "attribution": None,
        "terms": None,
        "terms_reference": None,
        "status": "unknown",
        "exclusion_reason": None,
    } | changes


@pytest.fixture
def document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "collections": [
            {
                "provider": "zenodo",
                "collection_id": "15696105",
                "revision": "v4",
                "archive_path": "videos.zip",
                "archive_md5": "95eae83aceb2d12803f5f567c31060a9",
                "videos": [
                    _video("videos/b.mp4", status="candidate", terms="MIT"),
                    _video("videos/a.mp4"),
                ],
            },
            {
                "provider": "huggingface",
                "collection_id": "wayneballard/drone-detection-dataset",
                "revision": "a" * 40,
                "archive_path": None,
                "archive_md5": None,
                "videos": [
                    _video("insects/a.mp4", status="excluded", exclusion_reason="unknown rights")
                ],
            },
        ],
    }


def _write(path: Path, document: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(document), encoding="ascii")
    return path


def test_inventory_is_deterministic_and_preserves_unknowns(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    first = _write(tmp_path / "one.yaml", document)
    reordered = copy.deepcopy(document)
    reordered["collections"].reverse()
    reordered["collections"][1]["videos"].reverse()
    second = _write(tmp_path / "two.yaml", reordered)
    out = tmp_path / "out.json"
    one = inventory_sources(first, out)
    two = inventory_sources(second, out)
    data = json.loads(out.read_text(encoding="ascii"))
    assert one.digest == two.digest and two.status == "unchanged"
    assert data["collections"][0]["provider"] == "huggingface"
    assert [v["path"] for v in data["collections"][1]["videos"]] == ["videos/a.mp4", "videos/b.mp4"]
    assert one.to_record()["source_inventory"]["terms"] == 2
    assert read_declaration(out, "declaration/source-inventory", 1) == data


@pytest.mark.parametrize("revision", ["main", "", "a" * 39, "A" * 40])
def test_refuses_unpinned_huggingface_revision(
    tmp_path: Path, document: dict[str, Any], revision: str
) -> None:
    document["collections"][1]["revision"] = revision
    with pytest.raises(CorpusRefusal):
        read_inventory(_write(tmp_path / "in.yaml", document))


def test_refuses_duplicate_paths_and_unsafe_paths(tmp_path: Path, document: dict[str, Any]) -> None:
    document["collections"][0]["videos"].append(_video("videos/a.mp4"))
    with pytest.raises(CorpusRefusal, match="repeats"):
        read_inventory(_write(tmp_path / "in.yaml", document))
    document["collections"][0]["videos"] = [_video("../escape.mp4")]
    with pytest.raises(CorpusRefusal, match="relative paths"):
        read_inventory(_write(tmp_path / "in.yaml", document))


def test_secrets_never_appear_in_refusals_or_output(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    secret = "hf_" + "a" * 24
    document["collections"][0]["videos"][0]["source_reference"] = (
        f"https://host/path?token={secret}"
    )
    out = tmp_path / "out.json"
    with pytest.raises(CorpusRefusal) as caught:
        inventory_sources(_write(tmp_path / "in.yaml", document), out)
    assert secret not in str(caught.value.to_record())
    assert not out.exists()


def test_conflicting_output_is_not_overwritten(tmp_path: Path, document: dict[str, Any]) -> None:
    path = _write(tmp_path / "in.yaml", document)
    out = tmp_path / "out.json"
    out.write_text("existing", encoding="ascii")
    with pytest.raises(CorpusRefusal):
        inventory_sources(path, out)
    assert out.read_text(encoding="ascii") == "existing"


def test_cli_writes_contract_example(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    from ss_track.cli import main

    example = Path(__file__).parents[2] / "schema/examples/declaration-source-inventory.json"
    out = tmp_path / "inventory.json"
    with caplog.at_level("INFO"):
        assert main(["discover", "inventory", "--file", str(example), "--out", str(out)]) == 0
    assert out.is_file()
    assert json.loads(caplog.records[-1].message)["source_inventory"]["video_count"] == 3


def test_missing_zenodo_archive_and_invalid_exclusion_are_explicit(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    document["collections"][0]["archive_md5"] = None
    result = inventory_sources(_write(tmp_path / "input.yaml", document), tmp_path / "out.json")
    assert result.to_record()["source_inventory"]["unresolved_zenodo_archive"] == 1
    document["collections"][0]["videos"][0]["exclusion_reason"] = "not excluded"
    with pytest.raises(CorpusRefusal, match="exclusion reason"):
        read_inventory(_write(tmp_path / "invalid.yaml", document))
