"""Failures, resume and provider protocol regressions."""

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources import provider_http, provider_listing
from ss_track.corpus.sources.provider_http import _SafeRedirect, download, parse_json
from ss_track.corpus.sources.provider_metadata import hf_files
from ss_track.corpus.sources.zenodo_splits import apply_splits


def test_interruption_removes_scratch_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Interrupted(io.BytesIO):
        def read(self, count: int = -1) -> bytes:
            raise KeyboardInterrupt()

    expected = hashlib.sha256(b"abc").hexdigest()
    target = tmp_path / "result"
    monkeypatch.setattr(provider_http, "_request", lambda url, token: Interrupted(b"abc"))
    with pytest.raises(KeyboardInterrupt):
        download("https://example.org/file", target, 3, "sha256", expected)
    assert not target.exists()
    assert not list(tmp_path.glob(".incoming-*"))
    monkeypatch.setattr(provider_http, "_request", lambda url, token: io.BytesIO(b"abc"))
    assert download("https://example.org/file", target, 3, "sha256", expected) == expected
    target.write_bytes(b"bad")
    with pytest.raises(CorpusRefusal) as caught:
        download("https://example.org/file", target, 3, "sha256", expected)
    assert caught.value.code == RefusalCode.SOURCE_HASH_MISMATCH
    assert target.read_bytes() == b"bad"


def test_git_blob_hash_and_mismatched_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    oid = hashlib.sha1(b"blob 3\0abc", usedforsecurity=False).hexdigest()
    monkeypatch.setattr(provider_http, "_request", lambda url, token: io.BytesIO(b"abc"))
    digest = download("https://example.org/file", tmp_path / "file", 3, "git-sha1", oid)
    assert digest == hashlib.sha256(b"abc").hexdigest()
    monkeypatch.setattr(provider_http, "_request", lambda url, token: io.BytesIO(b"abcd"))
    with pytest.raises(CorpusRefusal, match="size"):
        download("https://example.org/file", tmp_path / "other", 3, "git-sha1", oid)


def test_paginated_tree_and_unsafe_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "https://huggingface.co/api/datasets/owner/repo/tree/" + "a" * 40
    entries = [{"type": "file", "path": "a.mp4", "size": 1, "oid": "b" * 40}]
    calls: list[str] = []

    def read(url: str, token: str | None) -> tuple[object, str | None]:
        calls.append(url)
        return (entries, f'<{base}?cursor=next>; rel="next"') if len(calls) == 1 else ([], None)

    monkeypatch.setattr(provider_listing, "read_json", read)
    assert set(provider_listing.huggingface_listing("owner/repo", "a" * 40, None)) == {"a.mp4"}
    assert len(calls) == 2
    monkeypatch.setattr(
        provider_listing,
        "read_json",
        lambda url, token: ([], '<https://evil.invalid/>; rel="next"'),
    )
    with pytest.raises(CorpusRefusal, match="pagination"):
        provider_listing.huggingface_listing("owner/repo", "a" * 40, None)


def test_redirect_does_not_forward_token_to_another_host() -> None:
    request = Request("https://huggingface.co/x", headers={"Authorization": "Bearer hf_secret"})
    redirected = _SafeRedirect().redirect_request(
        request, None, 302, "Found", {}, "https://cdn.example/x"
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None
    with pytest.raises(CorpusRefusal, match="unsafe"):
        _SafeRedirect().redirect_request(request, None, 302, "Found", {}, "http://cdn.example/x")


def test_provider_and_split_mismatches_are_refused(tmp_path: Path) -> None:
    entry = {
        "type": "file",
        "path": "a.mp4",
        "size": 3,
        "oid": "b" * 40,
        "lfs": {"oid": "c" * 64, "size": 4},
    }
    with pytest.raises(CorpusRefusal):
        hf_files([[entry]])
    entry["lfs"]["size"] = 3
    with pytest.raises(CorpusRefusal):
        hf_files([[entry, entry]])
    path = tmp_path / "splits.json"
    path.write_text(json.dumps({"train_set": ["missing"]}), encoding="ascii")
    with pytest.raises(CorpusRefusal, match="mismatched"):
        apply_splits({"videos": [{"path": "a.mp4", "upstream_split": None}]}, path)


@pytest.mark.parametrize("payload", [b'{"size": 1, "size": 2}', b'{"value": NaN}'])
def test_provider_json_rejects_ambiguous_facts(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_json(payload)
