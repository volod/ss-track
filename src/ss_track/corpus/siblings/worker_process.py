"""Run the embedding worker in its own process and speak its protocol, with a deadline on each answer.

The worker runs under the sibling environment's interpreter with `-I`, an explicit environment and
an empty working directory, so neither project reads the other's settings. Its standard error goes
to a file, whose tail a refusal quotes; its standard output carries only the protocol. A worker that
stops, hangs, or answers with less than it announced is `WORKER_FAILED`, and is never waited on
beyond its deadline.
"""

import json
import os
import selectors
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import IO, Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

WORKER_SCRIPT = Path(__file__).with_name("perception_worker.py")
DEFAULT_TIMEOUT_SEC = 900.0
_READ_BYTES = 1 << 20
_MAX_LINE_BYTES = 1 << 24
_STDERR_TAIL_BYTES = 4096
_KILL_WAIT_SEC = 10.0
# Codes a worker may refuse with; anything else it says is a failure of the worker itself.
WORKER_CODES = frozenset(
    {RefusalCode.EXTRACTOR_UNPINNED, RefusalCode.EXTRACTOR_INCOMPATIBLE, RefusalCode.WORKER_FAILED}
)


class WorkerProcess:
    """One running worker: send a message, receive its answer before a deadline."""

    def __init__(self, process: subprocess.Popen[bytes], stderr: IO[bytes], timeout: float) -> None:
        self._process = process
        self._stderr = stderr
        self._timeout = timeout
        self._buffer = bytearray()
        assert process.stdout is not None and process.stdin is not None
        self._out = process.stdout
        self._in = process.stdin

    def send(self, header: Mapping[str, Any], payload: bytes = b"") -> None:
        """Write one message, announcing its bytes."""
        body = dict(header) | ({"bytes": len(payload)} if payload else {})
        try:
            self._in.write(json.dumps(body, sort_keys=True).encode("ascii") + b"\n" + payload)
            self._in.flush()
        except BrokenPipeError as error:
            raise self.failed("the worker stopped reading") from error

    def receive(self) -> tuple[dict[str, Any], bytes]:
        """Read one answer, refusing a refusal, a stopped or slow worker and a short answer."""
        deadline = time.monotonic() + self._timeout
        line = self._read_line(deadline)
        try:
            header = json.loads(line)
        except ValueError as error:
            raise self.failed("the worker wrote something other than the protocol") from error
        if not isinstance(header, dict):
            raise self.failed("the worker wrote something other than the protocol")
        payload = self._read_exact(int(header.get("bytes", 0)), deadline)
        if header.get("status") == "refused":
            raise self._refusal(header)
        return header, payload

    def _refusal(self, header: Mapping[str, Any]) -> CorpusRefusal:
        code = header.get("code")
        details: dict[str, JsonValue] = dict(header.get("details") or {})
        message = str(header.get("message", "the worker refused"))
        if code in WORKER_CODES:
            return CorpusRefusal(RefusalCode(code), message, details | self._tail())
        return self.failed(message)

    def _fill(self, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        with selectors.DefaultSelector() as selector:
            selector.register(self._out, selectors.EVENT_READ)
            if remaining <= 0 or not selector.select(remaining):
                raise self.failed(f"the worker did not answer within {self._timeout:g} s")
        chunk = os.read(self._out.fileno(), _READ_BYTES)
        if not chunk:
            raise self.failed("the worker ended before its answer was complete")
        self._buffer += chunk

    def _read_line(self, deadline: float) -> bytes:
        while (end := self._buffer.find(b"\n")) < 0:
            if len(self._buffer) > _MAX_LINE_BYTES:
                raise self.failed("the worker wrote a line longer than the protocol allows")
            self._fill(deadline)
        line = bytes(self._buffer[:end])
        del self._buffer[: end + 1]
        return line

    def _read_exact(self, size: int, deadline: float) -> bytes:
        while len(self._buffer) < size:
            self._fill(deadline)
        payload = bytes(self._buffer[:size])
        del self._buffer[:size]
        return payload

    def _tail(self) -> dict[str, JsonValue]:
        self._stderr.flush()
        self._stderr.seek(0, os.SEEK_END)
        size = self._stderr.tell()
        self._stderr.seek(max(0, size - _STDERR_TAIL_BYTES))
        text = self._stderr.read().decode("ascii", errors="replace")
        return {"worker_stderr_tail": text, "worker_exit": self._process.poll()}

    def failed(self, message: str) -> CorpusRefusal:
        """Build the refusal for a worker that did not keep the protocol, quoting its stderr."""
        self.stop()
        return CorpusRefusal(RefusalCode.WORKER_FAILED, message, self._tail())

    def stop(self) -> None:
        """End the worker, killing it when it does not exit by itself."""
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait(_KILL_WAIT_SEC)

    def close(self) -> None:
        """Ask the worker to exit, then make sure it did."""
        if self._process.poll() is None:
            try:
                self.send({"op": "close"})
                self._in.close()
                self._process.wait(_KILL_WAIT_SEC)
            except (CorpusRefusal, subprocess.TimeoutExpired, OSError):
                pass
        self.stop()


@contextmanager
def started_worker(
    python: Path,
    environment: Callable[[Path], Mapping[str, str]],
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> Iterator[WorkerProcess]:
    """Start the worker in an empty working directory and stop it however the block ends.

    `environment` builds the worker's whole environment from that directory, which also serves as
    the sibling's data and checkpoint directory, so nothing it finds there was put there before.
    """
    with TemporaryDirectory(prefix="ss-track-worker-") as neutral, TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(
                [str(python), "-I", str(WORKER_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                cwd=neutral,
                env=dict(environment(Path(neutral))),
            )
        except OSError as error:
            raise CorpusRefusal(
                RefusalCode.WORKER_FAILED,
                f"cannot start the embedding worker: {error}",
                {"python": str(python)},
            ) from error
        worker = WorkerProcess(process, stderr, timeout)
        try:
            yield worker
        finally:
            worker.close()
