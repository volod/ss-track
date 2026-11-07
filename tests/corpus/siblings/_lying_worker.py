"""A worker that breaks the protocol in one way, named in `$HF_HOME/lie.json`, to test ss-track's checks.

The real worker checks its own rows before it answers, so these lies can only come from a worker
that does not: a defective or substituted script. ss-track must refuse each one itself.
"""

import json
import os
import sys
from pathlib import Path

LIE = json.loads((Path(os.environ["HF_HOME"]) / "lie.json").read_text())["lie"]
DIMENSIONS = 8


def send(header: dict[str, object], payload: bytes = b"") -> None:
    if payload:
        header = {**header, "bytes": len(payload)}
    sys.stdout.buffer.write(json.dumps(header).encode() + b"\n" + payload)
    sys.stdout.buffer.flush()


def receive() -> tuple[dict[str, object], bytes]:
    header = json.loads(sys.stdin.buffer.readline())
    return header, sys.stdin.buffer.read(int(header.get("bytes", 0)))  # type: ignore[call-overload]


config, _ = receive()
if LIE == "garbage":
    sys.stdout.write("Downloading: model.pth\n")
    sys.stdout.flush()
    raise SystemExit(0)
if LIE == "unknown_code":
    send({"status": "refused", "code": "SOMETHING_ELSE", "message": "no", "details": {}})
    raise SystemExit(1)
if LIE == "incomplete":
    send({"status": "ready", "provenance": {"architecture": "ViT-B-16"}})
    raise SystemExit(0)
extractor: dict[str, object] = config["extractor"]  # type: ignore[assignment]
send(
    {
        "status": "ready",
        "provenance": {
            "architecture": extractor["model"],
            "package": {
                "name": "ss-perception",
                "version": "0.2.1",
                "commit": os.environ["LIE_COMMIT"],
            },
            "libraries": [{"name": "numpy", "version": "2"}],
            "weights": json.loads((Path(os.environ["HF_HOME"]) / "lie.json").read_text())[
                "weights"
            ],
            "device": "cpu",
            "dtype": "float32",
            "autocast": False,
            "preprocessing": {},
            "output": {"dimensions": DIMENSIONS, "normalized": True},
        },
    }
)
request, _ = receive()
frames: list[dict[str, object]] = request["frames"]  # type: ignore[assignment]
keys = [[frame["frame_index"], frame["sha256"]] for frame in frames]
row = b"\x00\x00\x80\x3f" + b"\x00" * 4 * (DIMENSIONS - 1)  # the unit vector (1, 0, ...)
rows = row * len(frames)
if LIE == "keys":
    keys = list(reversed(keys))
elif LIE == "partial":
    rows = rows[: -len(row)]
elif LIE == "nonunit":
    rows = b"\x00\x00\x00\x40" + rows[4:]  # first value 2.0
elif LIE == "short_payload":
    sys.stdout.buffer.write(
        json.dumps({"status": "rows", "keys": keys, "bytes": len(rows)}).encode() + b"\n" + rows[:8]
    )
    sys.stdout.buffer.flush()
    raise SystemExit(0)
send({"status": "rows", "keys": keys}, rows)
receive()
