"""Batch publication preserves snapshots on failure and rejects concurrent changes."""

from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility import batch_publish


def test_registry_write_failure_rolls_back_all_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_bytes(b"original registry")
    first, second = Path("first.binpb"), Path("second.binpb")
    (tmp_path / first).write_bytes(b"old")
    write = batch_publish.write_contract_file

    def fail_registry(root: Path, target: Path, payload: bytes) -> None:
        if target == registry:
            raise OSError("registry write failed")
        write(root, target, payload)

    monkeypatch.setattr(batch_publish, "write_contract_file", fail_registry)
    with pytest.raises(OSError, match="registry write failed"):
        batch_publish.publish_batch(
            tmp_path,
            {first: b"new", second: b"new"},
            {first: b"old", second: None},
            b"new registry",
            b"original registry",
        )
    assert (tmp_path / first).read_bytes() == b"old"
    assert not (tmp_path / second).exists()
    assert registry.read_bytes() == b"original registry"


def test_stale_registry_is_refused_before_any_file_is_written(tmp_path: Path) -> None:
    (tmp_path / "registry.yaml").write_bytes(b"concurrent registry")
    image = Path("image.binpb")
    (tmp_path / image).write_bytes(b"old")
    with pytest.raises(CorpusRefusal, match="registry changed during generation"):
        batch_publish.publish_batch(
            tmp_path, {image: b"new"}, {image: b"old"}, b"new registry", b"old registry"
        )
    assert (tmp_path / image).read_bytes() == b"old"
    assert (tmp_path / "registry.yaml").read_bytes() == b"concurrent registry"
