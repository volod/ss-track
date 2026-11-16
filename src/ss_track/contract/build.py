"""Regenerate event descriptor sets and Python bindings, and fail when they drift."""

import argparse
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from google.protobuf import descriptor_pb2

from ss_track.contract.breaking import (
    BUF_CONFIG,
    PACKAGE_IMPORTS,
    PACKAGES,
    PROTO_ROOT,
    breaking_findings,
    format_findings,
    lint_findings,
)
from ss_track.contract.image import fingerprints, package_urn
from ss_track.core.canonical import sha256_bytes
from ss_track.schema.compatibility.publishing import publish
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.contract import BASELINE_VERSION, DEVELOPMENT
from ss_track.schema.registry.stage import stage_findings
from ss_track.schema.registry.store import (
    REGISTRY_NAME,
    default_root,
    load_contract_set,
    registry_document,
)

_LOG = logging.getLogger(__name__)
_GEN_ROOT = Path(__file__).resolve().parent / "gen"
_IMPORT = re.compile(r"^import (\w+_pb2)(.*)$", re.MULTILINE)


def build_image(proto_root: Path, proto_file: str, destination: Path) -> None:
    """Build one package image, including the files it imports."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            str(_buf()),
            "build",
            ".",
            "--path",
            proto_file,
            "--config",
            "buf.yaml",
            "-o",
            str(destination),
            "--log-format",
            "text",
        ],
        cwd=proto_root,
    )
    _drop_dependency_comments(destination)


def generate_python(proto_root: Path, destination: Path) -> None:
    """Generate Python bindings and point their imports at this package."""
    destination.mkdir(parents=True, exist_ok=True)
    sources = sorted(proto_root.glob("*.proto"))
    _run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{proto_root}",
            f"--python_out={destination}",
            *(str(path) for path in sources),
        ]
    )
    for path in destination.glob("*_pb2.py"):
        path.write_text(
            _IMPORT.sub(r"from ss_track.contract.gen import \1\2", path.read_text()),
            encoding="utf-8",
        )


def write_artifacts(contracts_root: Path | None = None) -> list[str]:
    """Regenerate development images and pins; never replace a released image."""
    root = default_root() if contracts_root is None else contracts_root
    contracts = load_contract_set(root)
    problems = stage_findings(contracts)
    if problems:
        raise ValueError("; ".join(problems))
    notes = []
    for package in PACKAGES:
        with tempfile.TemporaryDirectory(prefix="ss-track-event-") as temporary:
            image = Path(temporary) / f"{package}.binpb"
            build_image(PROTO_ROOT, f"{package}.proto", image)
            payload = image.read_bytes()
        urn = package_urn(payload, package)
        version = urn.rsplit(":", 1)[-1]
        target = root / "event" / package / f"{version}.binpb"
        if contracts.stage == DEVELOPMENT:
            if version != BASELINE_VERSION:
                raise ValueError(f"event/{package}: development requires {BASELINE_VERSION}")
            _repin(root, package, version, payload, urn)
        elif target.is_file() and target.read_bytes() != payload:
            raise ValueError(f"{target}: frozen descriptor differs; bump the contract URN")
        elif not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        structure, meaning = fingerprints(payload, urn)
        notes.append(f"{package} {version} structure {structure} meaning {meaning}")
    generate_python(PROTO_ROOT, _GEN_ROOT)
    return notes


def _repin(root: Path, package: str, version: str, payload: bytes, urn: str) -> None:
    original = (root / REGISTRY_NAME).read_bytes()
    registry = registry_document(original)
    entries = [
        item
        for item in registry["contracts"]
        if item["family"] == "event" and item["id"] == package
    ]
    if len(entries) != 1 or len(entries[0]["versions"]) != 1:
        raise ValueError(f"event/{package}: expected one registered development version")
    entry = entries[0]["versions"][0]
    if entry["version"] != version:
        raise ValueError(f"event/{package}: registry version does not match {version}")
    structure, meaning = fingerprints(payload, urn)
    relative = Path("event") / package / f"{version}.binpb"
    if (
        entry["file_sha256"] == sha256_bytes(payload)
        and entry["fingerprints"] == {"structure": structure, "meaning": meaning}
        and (root / relative).is_file()
        and (root / relative).read_bytes() == payload
    ):
        return
    entry["file_sha256"] = sha256_bytes(payload)
    entry["fingerprints"] = {"structure": structure, "meaning": meaning}
    written = yaml.safe_dump(registry, sort_keys=False, allow_unicode=False).encode("ascii")
    with tempfile.TemporaryDirectory(prefix="ss-track-event-set-") as temporary:
        staged = Path(temporary) / "contracts"
        shutil.copytree(root, staged)
        (staged / relative).write_bytes(payload)
        (staged / REGISTRY_NAME).write_bytes(written)
        findings = check_contract_set(staged)
        if findings:
            raise ValueError("event generation refused: " + "; ".join(findings))
    publish(root, relative, payload, written, original, replace=True)


def drift_findings(contracts_root: Path | None = None) -> list[str]:
    """Return descriptor, binding, lint and breaking drift against the frozen set."""
    root = default_root() if contracts_root is None else contracts_root
    contracts = load_contract_set(root)
    findings = [*check_contract_set(root), *lint_findings(), *format_findings()]
    with tempfile.TemporaryDirectory(prefix="ss-track-event-") as temporary:
        base = Path(temporary)
        generated = base / "gen"
        try:
            generate_python(PROTO_ROOT, generated)
        except (RuntimeError, FileNotFoundError) as error:
            return [*findings, str(error)]
        findings += _python_drift(generated)
        for package in PACKAGES:
            findings += _package_drift(base, root, package, contracts.stage != DEVELOPMENT)
    return findings


def _package_drift(
    base: Path, contracts_root: Path, package: str, check_breaking: bool
) -> list[str]:
    image = base / f"{package}.binpb"
    try:
        build_image(PROTO_ROOT, f"{package}.proto", image)
        payload = image.read_bytes()
        urn = package_urn(payload, package)
    except (RuntimeError, FileNotFoundError, ValueError) as error:
        return [f"event/{package}: {error}"]
    version = urn.rsplit(":", 1)[-1]
    frozen = contracts_root / "event" / package / f"{version}.binpb"
    findings = []
    if not frozen.is_file():
        return [f"event/{package} {version}: frozen descriptor is missing"]
    if frozen.read_bytes() != payload:
        findings.append(f"event/{package} {version}: descriptor drifted from proto")
    if not check_breaking:
        return findings
    candidate = base / package
    for name in PACKAGE_IMPORTS[package]:
        destination = candidate / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(PROTO_ROOT / name, destination)
    shutil.copy(BUF_CONFIG, candidate / "buf.yaml")
    findings += [
        f"event/{package}: {item}"
        for item in breaking_findings(candidate, frozen, candidate / "buf.yaml")
    ]
    return findings


def _python_drift(generated: Path) -> list[str]:
    expected = {path.name: path.read_bytes() for path in generated.glob("*_pb2.py")}
    found = {path.name: path.read_bytes() for path in _GEN_ROOT.glob("*_pb2.py")}
    findings = [
        f"binding {name} drifted"
        for name in sorted(set(expected) | set(found))
        if expected.get(name) != found.get(name)
    ]
    return findings


def _buf() -> Path:
    from ss_track.contract.breaking import buf_executable

    return buf_executable()


def _drop_dependency_comments(image: Path) -> None:
    """Drop source locations of imported well-known files. Event comments stay."""
    parsed = descriptor_pb2.FileDescriptorSet()
    parsed.ParseFromString(image.read_bytes())
    for item in parsed.file:
        if not item.package.startswith("ss_track.event."):
            item.ClearField("source_code_info")
    image.write_bytes(parsed.SerializeToString())


def _run(command: list[str], cwd: Path | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(detail or f"{command[0]} exited {completed.returncode}")


def main(argv: list[str] | None = None) -> int:
    """Regenerate the artifacts, or fail when the committed ones drifted."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        for note in write_artifacts():
            _LOG.info("%s", note)
        return 0
    findings = drift_findings()
    for finding in findings:
        _LOG.error("ERROR: %s", finding)
    _LOG.info("[event schema] %d finding(s)", len(findings))
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
