"""The ss-perception embedding worker, which ss-track runs inside the sibling's pinned environment.

It is one file because `python -I` runs it by path with no package around it.

It imports nothing from ss-track, because that environment holds the sibling and not ss-track, and
ss-track never imports the sibling. ss-track starts it as `python -I <this file>` with an explicit
environment and an empty working directory, one process per extractor, and speaks over standard
input and the standard output descriptor it inherits: one JSON line per message, followed by the
raw bytes it announces. Each guard below neutralises a defect the sibling study found in the pinned
release, and `tests/corpus/siblings/test_sibling_defects.py` fails once that release loses one:

- Importing the sibling settings loads `.env` files and adds variables. Every value ss-track set
  must come back unchanged, and opening `.env` or `.env.local` is refused at any path.
- A weight or hub download writes its progress line on standard output (torch.hub does, even when
  the connection then fails). Descriptor 1 moves to standard error before anything is imported;
  the protocol keeps its own copy.
- `DINO_CHECKPOINT` or an `active_checkpoint.txt` loads an adapted checkpoint unrecorded, and a
  missing file keeps the base weights. Any configured checkpoint is refused.
- A CUDA out-of-memory error moves the model to the CPU for the rest of the run. The model's device
  is checked after loading and after every batch.
- Weights resolve from a branch. No network connection is allowed, and every weight file loaded
  must have an immutable revision: a Hugging Face snapshot commit or the digest of a torch.hub tree.
"""

import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import socket
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, BinaryIO, NoReturn

PROTOCOL = 1
UNPINNED = "EXTRACTOR_UNPINNED"
INCOMPATIBLE = "EXTRACTOR_INCOMPATIBLE"
FAILED = "WORKER_FAILED"
ENV_FILES = (".env", ".data/.env", ".data/.env.local")
WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pth", ".pt", ".ckpt")
LIBRARIES = (
    "huggingface-hub",
    "numpy",
    "open-clip-torch",
    "pillow",
    "safetensors",
    "timm",
    "torch",
    "torchvision",
)
CONFIG_MODULE = "selfsuvis.pipeline.core.config"
EMBEDDERS = {
    "openclip": ("selfsuvis.models.openclip_model", "OpenCLIPEmbedder"),
    "dino": ("selfsuvis.models.dino_model", "DINOEmbedder"),
}
NORM_TOLERANCE = 1e-3
HUB_CODE = "hubconf"
_SOURCE_SUFFIX = ".py"
_BYTECODE_DIRECTORY = "__pycache__"
SNAPSHOTS = "snapshots"
REPO_PREFIX = "models--"


class Refused(Exception):
    """A reason this worker cannot return rows that ss-track could trust."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class Channel:
    """The protocol: JSON lines and announced bytes over standard input and a saved descriptor."""

    def __init__(self) -> None:
        self._out: BinaryIO = os.fdopen(os.dup(1), "wb")
        os.dup2(2, 1)  # anything a library prints now reaches standard error, not the protocol
        self._in: BinaryIO = sys.stdin.buffer

    def receive(self) -> tuple[dict[str, Any], bytes]:
        line = self._in.readline()
        if not line:
            raise SystemExit(0)  # ss-track closed the pipe: nothing more to do
        header: dict[str, Any] = json.loads(line)
        size = int(header.get("bytes", 0))
        payload = self._in.read(size) if size else b""
        if len(payload) != size:
            raise Refused(FAILED, "the request ended before its announced bytes")
        return header, payload

    def send(self, header: dict[str, Any], payload: bytes = b"") -> None:
        if payload:
            header = {**header, "bytes": len(payload)}
        self._out.write(json.dumps(header, sort_keys=True).encode("ascii") + b"\n" + payload)
        self._out.flush()


class OpenedWeights:
    """Record every weight file the sibling opens, through Python and through safetensors."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self.active = False

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.fsdecode(args[0])
        if Path(path).name in {".env", ".env.local"}:
            raise Refused(UNPINNED, "the sibling tried to read an environment file", {})
        if self.active:
            self.note(path)

    def note(self, path: str) -> None:
        if (path.endswith(WEIGHT_SUFFIXES) or hub_tree(path)) and path not in self.paths:
            self.paths.append(path)

    def watch_safetensors(self) -> None:
        """safetensors opens files in Rust, which no audit event reports."""
        try:
            module = importlib.import_module("safetensors.torch")
        except ImportError:
            return
        for name in ("load_file", "safe_open"):
            original = getattr(module, name, None)
            if original is not None:
                setattr(module, name, self._noting(original))
        safetensors = importlib.import_module("safetensors")
        original = getattr(safetensors, "safe_open", None)
        if original is not None:
            setattr(safetensors, "safe_open", self._noting(original))  # noqa: B010

    def _noting(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def noted(filename: Any, *args: Any, **kwargs: Any) -> Any:
            if self.active:
                self.note(os.fspath(filename))
            return original(filename, *args, **kwargs)

        return noted


def refuse_network() -> None:
    """Make any download fail loudly instead of resolving weights from a branch."""

    def refused(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise OSError("ss-track worker: network access is refused; weights must be cached")

    socket.socket.connect = refused  # type: ignore[method-assign]
    socket.socket.connect_ex = refused  # type: ignore[method-assign]
    socket.create_connection = refused


def hub_tree(opened: str) -> Path | None:
    """Return the torch.hub tree whose `hubconf` was imported, from its source or its bytecode."""
    path = Path(opened)
    if path.name == HUB_CODE + _SOURCE_SUFFIX:
        return path.parent
    if path.parent.name == _BYTECODE_DIRECTORY and path.name.startswith(HUB_CODE + "."):
        return path.parent.parent
    return None


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def tree_digest(directory: Path) -> str:
    """Hash a torch.hub code tree, whose archive records no commit, by every file's path and bytes."""
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(directory).as_posix().encode("utf-8") + b"\0")
            digest.update(sha256_file(path).encode("ascii") + b"\n")
    return f"tree-sha256:{digest.hexdigest()}"


def weight_entry(opened: str, hub_trees: list[Path]) -> dict[str, Any]:
    """Name one weight file by where it resolved from, refusing one with no immutable revision."""
    path = Path(opened)
    parts = path.parts
    if SNAPSHOTS in parts:
        at = parts.index(SNAPSHOTS)
        repo = parts[at - 1] if at > 0 else ""
        if repo.startswith(REPO_PREFIX) and at + 1 < len(parts):
            name = repo.removeprefix(REPO_PREFIX).replace("--", "/")
            return _entry(name, parts[at + 1], path)
    if len(hub_trees) == 1:
        tree = hub_trees[0]
        return _entry(f"{tree.name}:{path.name}", tree_digest(tree), path)
    raise Refused(
        UNPINNED,
        "a weight file was loaded from no immutable revision",
        {"path": opened, "hub_trees": [str(tree) for tree in hub_trees]},
    )


def _entry(name: str, revision: str, path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "name": name,
        "revision": revision,
        "sha256": sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def loaded_weights(opened: OpenedWeights) -> list[dict[str, Any]]:
    hub_trees = sorted({tree for path in opened.paths if (tree := hub_tree(path)) is not None})
    files = [path for path in opened.paths if path.endswith(WEIGHT_SUFFIXES)]
    if not files:
        raise Refused(UNPINNED, "the extractor loaded no weight file this worker could see")
    entries: dict[str, dict[str, Any]] = {}
    for path in files:
        entry = weight_entry(path, hub_trees)
        if entry["name"] in entries and entries[entry["name"]] != entry:
            raise Refused(
                UNPINNED,
                "two weight files resolve under one name, so neither can be pinned alone",
                {"name": entry["name"]},
            )
        entries[entry["name"]] = entry
    return [entries[name] for name in sorted(entries)]


def check_environment(before: dict[str, str], settings: Any) -> None:
    changed = sorted(key for key, value in before.items() if os.environ.get(key) != value)
    if changed:
        raise Refused(
            UNPINNED, "importing the sibling settings changed the environment", {"keys": changed}
        )
    checkpoint = str(getattr(settings, "DINO_CHECKPOINT", "") or "")
    active = Path(str(getattr(settings, "SUP_CHECKPOINT_DIR", "") or ".")) / "active_checkpoint.txt"
    if checkpoint or active.exists():
        raise Refused(
            UNPINNED,
            "an adapted DINO checkpoint is configured; adapted checkpoints are not used",
            {
                "dino_checkpoint": checkpoint,
                "active_checkpoint": str(active) if active.exists() else None,
            },
        )
    if getattr(settings, "USE_FP16", False):
        raise Refused(INCOMPATIBLE, "mixed precision is on; the adapter records float32 rows only")


def package_facts(name: str) -> dict[str, str]:
    try:
        distribution = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError as error:
        raise Refused(UNPINNED, f"{name} is not installed in the worker environment") from error
    raw = distribution.read_text("direct_url.json")
    commit = json.loads(raw).get("vcs_info", {}).get("commit_id") if raw else None
    if not commit:
        raise Refused(UNPINNED, f"{name} records no commit; install it from a Git revision")
    return {"name": name, "version": distribution.version, "commit": str(commit)}


def libraries() -> list[dict[str, str]]:
    found = []
    for name in LIBRARIES:
        try:
            found.append({"name": name, "version": importlib.metadata.version(name)})
        except importlib.metadata.PackageNotFoundError:
            continue
    return found


def _square(value: Any) -> tuple[int, int] | None:
    """Return a size as height and width, or None for one int, which means the short side."""
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return int(value[0]), int(value[-1])
    return None


def _side(value: Any) -> int:
    return int(value[0]) if isinstance(value, (list, tuple)) else int(value)


def _resize(transform: Any) -> dict[str, Any]:
    exact = _square(transform.size)
    side = _side(transform.size)
    interpolation = transform.interpolation
    return {
        "resize": "short_side" if exact is None else "exact",
        "interpolation": str(getattr(interpolation, "value", interpolation)).lower(),
        "input": exact or (side, side),
    }


def _crop(transform: Any) -> dict[str, Any]:
    side = _side(transform.size)
    return {"crop": "center", "input": _square(transform.size) or (side, side)}


def _normalize(transform: Any) -> dict[str, Any]:
    return {
        "mean": [float(value) for value in transform.mean],
        "std": [float(value) for value in transform.std],
    }


# torchvision transforms by class name; anything else (ToTensor, an RGB conversion) changes no fact.
TRANSFORMS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "Resize": _resize,
    "CenterCrop": _crop,
    "Normalize": _normalize,
}


def preprocessing(transforms: list[Any]) -> dict[str, Any]:
    """State a torchvision pipeline: its resize, crop, filter, input size and normalisation."""
    found: dict[str, Any] = {"resize": "none", "crop": "none"}
    for transform in transforms:
        reader = TRANSFORMS.get(type(transform).__name__)
        if reader is not None:
            found |= reader(transform)
    if not {"interpolation", "input", "mean", "std"} <= found.keys():
        raise Refused(
            INCOMPATIBLE, "the embedder's preprocessing cannot be stated", {"found": sorted(found)}
        )
    height, width = found.pop("input")
    return {**found, "input_width": width, "input_height": height}


def device_of(embedder: Any) -> str:
    return str(next(iter(embedder.model.parameters())).device)


def dtype_of(embedder: Any) -> str:
    return str(next(iter(embedder.model.parameters())).dtype).removeprefix("torch.")


class Worker:
    """One pinned extractor, loaded once and asked for one batch of rows at a time."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.extractor: dict[str, Any] = config["extractor"]
        self.package: dict[str, str] = config["package"]
        self.embedder: Any = None
        self.device = ""

    def load(self) -> dict[str, Any]:
        present = [name for name in ENV_FILES if Path(name).exists()]
        if present:
            raise Refused(
                UNPINNED,
                "the working directory holds .env files the sibling would load",
                {"files": present},
            )
        refuse_network()
        opened = OpenedWeights()
        sys.addaudithook(opened.audit)
        before = dict(os.environ)
        settings = importlib.import_module(CONFIG_MODULE).settings
        check_environment(before, settings)
        package = package_facts(self.package["name"])
        opened.watch_safetensors()
        module_name, class_name = EMBEDDERS[self.extractor["kind"]]
        embedder_class = getattr(importlib.import_module(module_name), class_name)
        opened.active = True
        try:
            if self.extractor["kind"] == "dino":
                self.embedder = embedder_class(model_name=self.extractor["model"])
                architecture = str(self.embedder.model_name)
            else:
                self.embedder = embedder_class()
                architecture = str(settings.OPENCLIP_MODEL)
        except Exception as error:
            raise Refused(
                UNPINNED, f"the extractor did not load from the local cache: {error}"
            ) from error
        finally:
            opened.active = False
        self.device = self._require_device()
        return {
            "architecture": architecture,
            "package": package,
            "libraries": libraries(),
            "weights": loaded_weights(opened),
            "device": self.device,
            "dtype": dtype_of(self.embedder),
            "autocast": False,
            "preprocessing": preprocessing(list(self.embedder.preprocess.transforms)),
            "output": {"dimensions": int(self.embedder.image_dim()), "normalized": True},
        }

    def _require_device(self) -> str:
        device = device_of(self.embedder)
        requested = self.extractor["device"]
        if self.device and device != self.device:
            raise Refused(
                INCOMPATIBLE,
                "the model changed device during the run",
                {"loaded": self.device, "found": device},
            )
        if device.split(":")[0] != requested:
            raise Refused(
                INCOMPATIBLE,
                "the model is not on the requested device",
                {"requested": requested, "found": device},
            )
        if dtype_of(self.embedder) != "float32":
            raise Refused(
                INCOMPATIBLE, "the model is not float32", {"found": dtype_of(self.embedder)}
            )
        return device

    def embed(self, frames: list[dict[str, Any]], payload: bytes) -> bytes:
        image_module = importlib.import_module("PIL.Image")
        numpy = importlib.import_module("numpy")
        images = []
        offset = 0
        for frame in frames:
            size = frame["width"] * frame["height"] * 3
            chunk = payload[offset : offset + size]
            offset += size
            if hashlib.sha256(chunk).hexdigest() != frame["sha256"]:
                raise Refused(
                    FAILED,
                    "a frame's bytes do not match its hash",
                    {"frame_index": frame["frame_index"]},
                )
            images.append(image_module.frombytes("RGB", (frame["width"], frame["height"]), chunk))
        if offset != len(payload) or len(frames) > self.extractor["batch_size"]:
            raise Refused(FAILED, "the request does not hold one batch of the announced frames")
        rows = numpy.asarray(
            self.embedder.encode_images(images, batch_size=self.extractor["batch_size"])
        )
        self._require_device()
        expected = (len(frames), self.extractor["dimensions"])
        if tuple(rows.shape) != expected or not bool(numpy.isfinite(rows).all()):
            raise Refused(
                FAILED,
                "the extractor returned rows of another shape or a non-finite value",
                {"shape": list(rows.shape)},
            )
        norms = numpy.linalg.norm(rows.astype("float64"), axis=1)
        if not all(math.isclose(float(norm), 1.0, abs_tol=NORM_TOLERANCE) for norm in norms):
            raise Refused(FAILED, "the extractor returned rows that are not unit length")
        payload_out: bytes = rows.astype("<f4").tobytes()
        return payload_out


def serve(channel: Channel) -> Iterator[None]:
    config, _ = channel.receive()
    if config.get("protocol") != PROTOCOL:
        raise Refused(
            FAILED, f"ss-track speaks protocol {config.get('protocol')}, this worker {PROTOCOL}"
        )
    worker = Worker(config)
    channel.send({"status": "ready", "provenance": worker.load()})
    while True:
        request, payload = channel.receive()
        if request.get("op") == "close":
            return
        rows = worker.embed(request["frames"], payload)
        keys = [[frame["frame_index"], frame["sha256"]] for frame in request["frames"]]
        channel.send({"status": "rows", "keys": keys}, rows)
        yield


def main() -> int:
    channel = Channel()
    try:
        for _ in serve(channel):
            pass
    except Refused as refusal:
        channel.send(
            {
                "status": "refused",
                "code": refusal.code,
                "message": refusal.message,
                "details": refusal.details,
            }
        )
        return 1
    except Exception as error:  # anything else is a worker failure ss-track must see, not a hang
        channel.send(
            {
                "status": "refused",
                "code": FAILED,
                "message": f"{type(error).__name__}: {error}",
                "details": {},
            }
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
