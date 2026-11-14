import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ss_track.cli import main
from ss_track.core.paths import resolve_data_root
from ss_track.corpus.review.export import write_once
from ss_track.corpus.sources import provider_http
from tests.corpus.sources.test_acquisition import _inventory, _Response, _zip_bytes

root = resolve_data_root() / "self-supervised-corpus" / "acquisition-fixture-inputs"
root.mkdir(parents=True, exist_ok=True)
archive = _zip_bytes()
md5 = hashlib.md5(archive, usedforsecurity=False).hexdigest()
with TemporaryDirectory(dir=root, prefix=".incoming-") as directory:
    prepared = _inventory(Path(directory) / "zenodo.yaml", "zenodo", md5)
    zenodo = root / "zenodo.yaml"
    write_once(zenodo, prepared.read_bytes())
zenodo_metadata = {
    "id": 15696105,
    "metadata": {"version": "v4"},
    "files": [{"key": "videos.zip", "size": len(archive), "checksum": f"md5:{md5}"}],
}
payload = b"fixture-video"
sha = hashlib.sha256(payload).hexdigest()
hf_metadata = [
    {
        "type": "file",
        "path": "videos/a.mp4",
        "size": len(payload),
        "oid": "b" * 40,
        "lfs": {"oid": sha, "size": len(payload)},
    }
]
with TemporaryDirectory(dir=root, prefix=".incoming-") as directory:
    prepared = _inventory(Path(directory) / "hf.yaml", "huggingface")
    hf = root / "hf.yaml"
    write_once(hf, prepared.read_bytes())


def request(url, token):
    if "zenodo.org" in url:
        return _Response(json.dumps(zenodo_metadata).encode() if "/api/" in url else archive)
    return _Response(json.dumps(hf_metadata).encode() if "/api/" in url else payload)


provider_http._request = request
for provider, collection, inventory, run_id in [
    ("zenodo", "15696105", zenodo, "acquisition-zenodo-fixture-v2-20261108"),
    ("huggingface", "owner/repo", hf, "acquisition-hf-fixture-v2-20261108"),
]:
    argv = [
        "discover",
        "acquire",
        "--inventory",
        str(inventory),
        "--provider",
        provider,
        "--collection",
        collection,
        "--video",
        "videos/a.mp4",
        "--run-id",
        run_id,
        "--download-budget",
        "100000",
        "--extraction-budget",
        "100000",
        "--authorized",
    ]
    assert main(argv) == 0
    assert main(argv) == 0
