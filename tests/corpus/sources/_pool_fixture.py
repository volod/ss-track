"""Network-free acquisitions and a two-source pool declaration."""

import hashlib
from pathlib import Path

import yaml

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.corpus.records.kinds import SOURCE_ACQUISITION
from tests.corpus._media import expected_rgb, write_clip

RIGHTS = {
    "holder": "Fixture Operator",
    "basis": "licensed",
    "retention": "fixture retention",
    "retain_until": None,
    "derived_frames": True,
    "sharing": "restricted",
}
SENSITIVITY = {"level": "low"}
TERMS = "https://example.com/terms"
HF_METADATA = {
    "metadata/drone.yaml": (
        "path: videos/drone.mkv\nlicense: mit\nsource: https://example.com/drone\n"
        "annotation: annotations/drone.txt\n"
    ),
    "metadata/conflict-a.yaml": "path: videos/conflict.mkv\nlicense: mit\n",
    "metadata/conflict-b.yaml": "path: videos/conflict.mkv\nlicense: cc-1.0\n",
    "metadata/scenarios.yaml": "vocabulary:\n- birds\n",
    "metadata/sources.txt": (
        "https://example.com/bird - cc-1.0\n"
        "https://example.com/clip?page=1 - mit\n"
        "personal recordings\n"
        "https://example.com/unknown - mit\n"
    ),
    "metadata/videos.csv": (
        "name,license,extra\n"
        "videos/drone.mkv,mit,ignore\n"
        "videos/missing.mkv,mit,ignore\n"
        "no_drone/birds_only/rgb/1,fuzzy-license,ignore\n"
    ),
    "metadata/labels.json": '{"label":"not-a-label-xyz"}\n',
    "metadata/secret.yaml": "path: videos/drone.mkv\nlicense: token=abcdefsecret\n",
}


def _video(path: str, **changes: object) -> dict[str, object]:
    recorded = {
        "path": path,
        "source_reference": None,
        "annotation_reference": None,
        "upstream_split": None,
        "attribution": "Fixture",
        "terms": "fixture terms",
        "terms_reference": TERMS,
        "status": "candidate",
        "exclusion_reason": None,
    }
    return recorded | changes


def _clip(path: Path, shift: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_clip(
        path,
        frames=4,
        content=lambda index, width, height, shift=shift: expected_rgb(
            index + shift, width, height
        ),
    )


def publish(
    data_root: Path,
    run_id: str,
    provider: str,
    collection_id: str,
    revision: str,
    files: dict[str, bytes],
    inventory: list[dict[str, object]],
    metadata: dict[str, bytes] | None = None,
) -> None:
    """Write one sealed acquisition whose local bytes match the record."""
    root = data_root / "self-supervised-corpus" / run_id
    video_rows = [
        _store(root, f"media/{path}", path, payload) for path, payload in sorted(files.items())
    ]
    metadata_rows = [
        _store(root, path, path, payload) for path, payload in sorted((metadata or {}).items())
    ]
    document = {
        "schema_version": 1,
        "collections": [
            {
                "provider": provider,
                "collection_id": collection_id,
                "revision": revision,
                "archive_path": "videos.zip" if provider == "zenodo" else None,
                "archive_md5": "95eae83aceb2d12803f5f567c31060a9" if provider == "zenodo" else None,
                "videos": inventory,
            }
        ],
    }
    payload = canonical_json(document)
    (root / "inventory.json").write_bytes(payload)
    digest = sha256_bytes(payload)
    body = {
        **SOURCE_ACQUISITION.stamp(),
        "provider": provider,
        "collection_id": collection_id,
        "revision": revision,
        "inventory_sha256": digest,
        "input_inventory_sha256": digest,
        "archive_md5": document["collections"][0]["archive_md5"],
        "archive_sha256": None,
        "split_md5": None,
        "split_sha256": None,
        "videos": video_rows,
        "metadata_files": metadata_rows,
    }
    write_sealed(root / "acquisition.json", seal(body))


def _store(root: Path, local: str, path: str, payload: bytes) -> dict[str, object]:
    target = root / local
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {
        "path": path,
        "local_path": local,
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "git_oid": None,
        "lfs_sha256": None,
    }


def combined_pool(tmp_path: Path, data_root: Path) -> Path:
    """Publish the two-source fixture and return its pool declaration."""
    bird = tmp_path / "bird.mkv"
    plain = tmp_path / "plain.mkv"
    drone = tmp_path / "drone.mkv"
    _clip(bird, 0)
    _clip(plain, 3)
    _clip(drone, 7)
    bird_bytes = bird.read_bytes()
    publish(
        data_root,
        "acq-zenodo",
        "zenodo",
        "15696105",
        "v4",
        {
            "videos/bird.mkv": bird_bytes,
            "videos/plain.mkv": plain.read_bytes(),
            "videos/locked.mkv": b"locked-bytes",
        },
        [
            _video(
                "videos/bird.mkv",
                attribution="Zenodo bird",
                source_reference="https://example.com/bird",
                annotation_reference="annotations/bird.json",
                upstream_split="train_set",
            ),
            _video("videos/plain.mkv", attribution="Zenodo plain", upstream_split="train_set"),
            _video("videos/locked.mkv", attribution="Zenodo locked", upstream_split="test_set"),
        ],
    )
    metadata = {path: text.encode("ascii") for path, text in HF_METADATA.items()}
    metadata["metadata/odd.yaml"] = b"path: videos/drone.mkv\nnote: caf\xc3\xa9\n"
    publish(
        data_root,
        "acq-hf",
        "huggingface",
        "owner/dataset",
        "a" * 40,
        {
            "videos/bird.mkv": bird_bytes,
            "videos/drone.mkv": drone.read_bytes(),
            "videos/conflict.mkv": b"conflict-bytes",
        },
        [
            _video(
                "videos/bird.mkv",
                attribution="HF bird",
                source_reference="https://example.com/bird",
            ),
            _video("videos/drone.mkv", attribution="HF drone"),
            _video("videos/conflict.mkv", attribution="HF conflict"),
        ],
        metadata,
    )
    declaration = {
        "schema_version": 1,
        "corpus_id": "combined-v1",
        "run_id": "pool-combined",
        "scenario_rights": {"sharing": "restricted", "max_sensitivity": "moderate"},
        "collections": [
            _declared(
                "acq-zenodo",
                {
                    "videos/bird.mkv": "development",
                    "videos/plain.mkv": "calibration",
                    "videos/locked.mkv": "development",
                },
            ),
            _declared(
                "acq-hf",
                {
                    "videos/bird.mkv": "development",
                    "videos/drone.mkv": "development",
                    "videos/conflict.mkv": "development",
                },
            ),
        ],
    }
    path = tmp_path / "pool.yaml"
    path.write_text(yaml.safe_dump(declaration, sort_keys=False), encoding="ascii")
    return path


def _declared(
    run_id: str, splits: dict[str, str], rights: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "rights": RIGHTS if rights is None else rights,
        "sensitivity": SENSITIVITY,
        "videos": [{"path": path, "split": split} for path, split in splits.items()],
    }


def write_pool(
    path: Path,
    run_id: str,
    collections: list[dict[str, object]],
    corpus_id: str = "combined-v1",
) -> Path:
    """Write a pool declaration that names `collections`."""
    document = {
        "schema_version": 1,
        "corpus_id": corpus_id,
        "run_id": run_id,
        "scenario_rights": {"sharing": "restricted", "max_sensitivity": "moderate"},
        "collections": collections,
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="ascii")
    return path
