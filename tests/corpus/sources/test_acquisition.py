"""Network-free provider acquisition, metadata, budgets, rights and replay."""

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.core.refusal import CorpusRefusal
from ss_track.corpus.records.kinds import SOURCE_ACQUISITION
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.sources import provider_http
from ss_track.corpus.sources.acquisition import AcquisitionRequest, acquire


class _Response(io.BytesIO):
    def __init__(self, payload: bytes, link: str | None = None) -> None:
        super().__init__(payload)
        self.headers = {"Link": link} if link else {}


def _video(path: str) -> dict[str, Any]:
    return {
        "path": path,
        "source_reference": None,
        "annotation_reference": None,
        "upstream_split": None,
        "attribution": "Creator",
        "terms": "licensed use",
        "terms_reference": "https://example.org/terms",
        "status": "candidate",
        "exclusion_reason": None,
    }


def _inventory(path: Path, provider: str, archive_md5: str | None = None) -> Path:
    doc = {
        "schema_version": 1,
        "collections": [
            {
                "provider": provider,
                "collection_id": "15696105" if provider == "zenodo" else "owner/repo",
                "revision": "v4" if provider == "zenodo" else "a" * 40,
                "archive_path": "videos.zip" if provider == "zenodo" else None,
                "archive_md5": archive_md5,
                "videos": [_video("videos/a.mp4")],
            }
        ],
    }
    path.write_text(yaml.safe_dump(doc), encoding="ascii")
    return path


def _request(
    path: Path, provider: str, *, authorized: bool = True, budget: int = 100000
) -> AcquisitionRequest:
    return AcquisitionRequest(
        path,
        provider,
        "15696105" if provider == "zenodo" else "owner/repo",
        ["videos/a.mp4"],
        "fixture",
        budget,
        budget,
        authorized,
    )


def _zip_bytes() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(zipfile.ZipInfo("videos/a.mp4"), b"abc")
        archive.writestr(zipfile.ZipInfo("videos/b.mp4"), b"def")
    return data.getvalue()


def test_zenodo_acquire_replay_and_enumerate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _zip_bytes()
    md5 = hashlib.md5(archive, usedforsecurity=False).hexdigest()
    inventory = _inventory(tmp_path / "inventory.yaml", "zenodo", md5)
    splits = json.dumps({"train_set": ["a"], "val_set": ["b"], "test_set": []}).encode()
    split_md5 = hashlib.md5(splits, usedforsecurity=False).hexdigest()
    metadata = {
        "id": 15696105,
        "metadata": {"version": "v4"},
        "files": [
            {"key": "videos.zip", "size": len(archive), "checksum": f"md5:{md5}"},
            {"key": "splits.json", "size": len(splits), "checksum": f"md5:{split_md5}"},
        ],
    }

    def fake(url: str, token: str | None) -> _Response:
        assert token is None
        if "/api/" in url:
            return _Response(json.dumps(metadata).encode())
        return _Response(splits if url.endswith("splits.json") else archive)

    monkeypatch.setattr(provider_http, "_request", fake)
    request = _request(inventory, "zenodo")
    first = acquire(request, tmp_path / "data")
    assert first.status == "written"
    record = read_sealed(first.path, SOURCE_ACQUISITION)
    assert record["archive_sha256"] == hashlib.sha256(archive).hexdigest()
    videos = json.loads((first.path.parent / "inventory.json").read_bytes())["collections"][0][
        "videos"
    ]
    assert [video["path"] for video in videos] == ["videos/a.mp4", "videos/b.mp4"]
    assert videos[1]["terms"] is None and videos[1]["status"] == "unknown"
    assert videos[0]["upstream_split"] == "train_set"
    assert videos[1]["upstream_split"] == "val_set"
    assert record["split_md5"] == split_md5
    leftover = first.path.parent / "scratch/.incoming-killed"
    leftover.write_bytes(b"partial")
    assert acquire(request, tmp_path / "data").status == "unchanged"
    assert not leftover.exists()
    (first.path.parent / "media/videos/a.mp4").write_bytes(b"conflict")
    with pytest.raises(CorpusRefusal, match="conflict"):
        acquire(request, tmp_path / "data")


def test_huggingface_lfs_auth_and_anonymous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = _inventory(tmp_path / "inventory.yaml", "huggingface")
    payload = b"abc"
    digest = hashlib.sha256(payload).hexdigest()
    metadata = [
        {
            "type": "file",
            "path": "videos/a.mp4",
            "size": 3,
            "oid": "b" * 40,
            "lfs": {"oid": digest, "size": 3},
        },
        {"type": "file", "path": "videos/b.mp4", "size": 3, "oid": "c" * 40},
    ]
    seen: list[str | None] = []

    def fake(url: str, token: str | None) -> _Response:
        seen.append(token)
        return _Response(json.dumps(metadata).encode() if "/api/" in url else payload)

    monkeypatch.setattr(provider_http, "_request", fake)
    monkeypatch.setenv("HF_TOKEN", "hf_" + "secret" * 4)
    result = acquire(_request(inventory, "huggingface"), tmp_path / "data")
    assert len(seen) == 2 and all(token == "hf_" + "secret" * 4 for token in seen)
    assert (result.path.parent / "media/videos/a.mp4").read_bytes() == payload
    assert b"hf_" not in result.path.read_bytes()
    assert b"hf_" not in (result.path.parent / "inventory.json").read_bytes()
    monkeypatch.delenv("HF_TOKEN")
    seen.clear()
    assert acquire(_request(inventory, "huggingface"), tmp_path / "data").status == "unchanged"
    assert seen == [None]


def test_refuses_rights_budget_and_mismatched_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = _inventory(tmp_path / "inventory.yaml", "huggingface")
    request = _request(inventory, "huggingface", authorized=False)
    with pytest.raises(CorpusRefusal, match="authorized"):
        acquire(request, tmp_path / "data")
    metadata = [{"type": "file", "path": "videos/a.mp4", "size": 3, "oid": "b" * 40}]
    monkeypatch.setattr(
        provider_http, "_request", lambda url, token: _Response(json.dumps(metadata).encode())
    )
    with pytest.raises(CorpusRefusal, match="budget"):
        acquire(_request(inventory, "huggingface", budget=2), tmp_path / "data")
    metadata[0]["path"] = "videos/missing.mp4"
    with pytest.raises(CorpusRefusal, match="match provider"):
        acquire(_request(inventory, "huggingface"), tmp_path / "data")


def test_cli_acquisition_reports_inventory_without_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from ss_track.cli import main

    inventory = _inventory(tmp_path / "inventory.yaml", "huggingface")
    digest = hashlib.sha256(b"abc").hexdigest()
    metadata = [
        {
            "type": "file",
            "path": "videos/a.mp4",
            "size": 3,
            "oid": "b" * 40,
            "lfs": {"oid": digest, "size": 3},
        }
    ]

    def fake(url: str, token: str | None) -> _Response:
        return _Response(json.dumps(metadata).encode() if "/api/" in url else b"abc")

    monkeypatch.setattr(provider_http, "_request", fake)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    secret = "hf_" + "z" * 24
    monkeypatch.setenv("HF_TOKEN", secret)
    with caplog.at_level("INFO"):
        result = main(
            [
                "discover",
                "acquire",
                "--inventory",
                str(inventory),
                "--provider",
                "huggingface",
                "--collection",
                "owner/repo",
                "--video",
                "videos/a.mp4",
                "--run-id",
                "fixture",
                "--download-budget",
                "3",
                "--extraction-budget",
                "3",
                "--authorized",
            ]
        )
    assert result == 0
    output = json.loads(caplog.records[-1].message)
    assert output["source_inventory"]["source_reference"] == 1
    assert output["source_inventory"]["video_count"] == 1
    assert secret not in caplog.text


def test_existing_run_refuses_different_request_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    inventory = _inventory(tmp_path / "inventory.yaml", "huggingface")
    digest = hashlib.sha256(b"abc").hexdigest()
    metadata = [
        {
            "type": "file",
            "path": "videos/a.mp4",
            "size": 3,
            "oid": "b" * 40,
            "lfs": {"oid": digest, "size": 3},
        }
    ]
    monkeypatch.setattr(
        provider_http,
        "_request",
        lambda url, token: _Response(json.dumps(metadata).encode() if "/api/" in url else b"abc"),
    )
    request = _request(inventory, "huggingface")
    acquire(request, tmp_path / "data")
    document = yaml.safe_load(inventory.read_text(encoding="ascii"))
    document["collections"][0]["videos"].append(_video("videos/b.mp4"))
    inventory.write_text(yaml.safe_dump(document), encoding="ascii")
    monkeypatch.setattr(
        provider_http, "_request", lambda url, token: pytest.fail("unexpected request")
    )
    with pytest.raises(CorpusRefusal, match="different acquisition"):
        acquire(replace(request, selection=["videos/b.mp4"]), tmp_path / "data")


def test_selects_verified_huggingface_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    inventory = _inventory(tmp_path / "inventory.yaml", "huggingface")
    media, description = b"abc", b"camera: example\n"
    files = {"videos/a.mp4": media, "metadata/a.yaml": description}
    metadata = [
        {
            "type": "file",
            "path": path,
            "size": len(payload),
            "oid": "b" * 40,
            "lfs": {"oid": hashlib.sha256(payload).hexdigest(), "size": len(payload)},
        }
        for path, payload in files.items()
    ]

    def fake(url: str, token: str | None) -> _Response:
        if "/api/" in url:
            return _Response(json.dumps(metadata).encode())
        return _Response(next(payload for path, payload in files.items() if url.endswith(path)))

    monkeypatch.setattr(provider_http, "_request", fake)
    request = replace(_request(inventory, "huggingface"), metadata=["metadata/a.yaml"])
    result = acquire(request, tmp_path / "data")
    record = read_sealed(result.path, SOURCE_ACQUISITION)
    assert (result.path.parent / "metadata/metadata/a.yaml").read_bytes() == description
    assert record["metadata_files"][0]["sha256"] == hashlib.sha256(description).hexdigest()
    with pytest.raises(CorpusRefusal, match="budget"):
        acquire(replace(request, run_id="small", download_budget=len(media)), tmp_path / "data")


def test_interrupted_run_refuses_a_different_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    inventory = _inventory(tmp_path / "inventory.yaml", "huggingface")
    document = yaml.safe_load(inventory.read_text(encoding="ascii"))
    document["collections"][0]["videos"].append(_video("videos/b.mp4"))
    inventory.write_text(yaml.safe_dump(document), encoding="ascii")
    request = _request(inventory, "huggingface")

    def interrupt(url: str, token: str | None) -> _Response:
        raise KeyboardInterrupt()

    monkeypatch.setattr(provider_http, "_request", interrupt)
    with pytest.raises(KeyboardInterrupt):
        acquire(request, tmp_path / "data")
    with pytest.raises(CorpusRefusal, match="different request"):
        acquire(replace(request, selection=["videos/b.mp4"]), tmp_path / "data")
