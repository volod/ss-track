"""Export a verified corpus as deterministic, local dataset discovery artifacts."""

import csv
import io
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.corpus.builder import load_corpus_manifest
from ss_track.corpus.descriptor_metadata import TABLES, metadata
from ss_track.corpus.descriptor_public import public_tables
from ss_track.corpus.fields import Fields, invalid
from ss_track.corpus.frame_set import require_frame_set
from ss_track.corpus.frames import (
    FRAME_BUNDLE,
    bundle_hash,
    frame_name,
    frames_root,
    require_bundle_place,
)
from ss_track.corpus.importer import MANIFEST_NAME
from ss_track.corpus.sealed import read_sealed
from ss_track.corpus.sources import load_source_record
from ss_track.corpus.staging import verify_corpus_frames
from ss_track.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema.enforce import read_declaration
from ss_track.schema.store import load_contract_set


@dataclass(frozen=True, slots=True)
class DescriptorResult:
    """Location of a written local descriptor."""

    corpus_id: str
    manifest_path: Path

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "status": "recorded",
            "corpus_id": self.corpus_id,
            "manifest_path": str(self.manifest_path),
        }


def _declaration(path: Path, public: bool) -> dict[str, str]:
    try:
        raw = read_declaration(path, "declaration/dataset", 1)
        fields = Fields(raw, "dataset")
        result = {
            name: fields.text(name)
            for name in ("title", "description", "license", "citation", "address")
        }
        result["publication_date"] = str(raw["publication_date"])
        return result
    except CorpusRefusal as error:
        if public:
            raise invalid("dataset declaration is invalid") from error
        raise


def _csv(records: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["record"])
    for record in records:
        writer.writerow(
            [json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))]
        )
    return buffer.getvalue().encode("ascii")


def _records(corpus: dict[str, Any], data_root: Path) -> dict[str, list[dict[str, Any]]]:
    streams, bundles, frames = [], [], []
    root = frames_root(data_root, corpus["corpus_id"])
    for stream in corpus["streams"]:
        source = load_source_record(stream["source_sha256"], data_root)
        if source["manifest_sha256"] != stream["source_manifest_sha256"]:
            raise CorpusRefusal(
                RefusalCode.SOURCE_RECORD_CHANGED, "source record changed during description"
            )
        streams.append({"stream": stream, "source": source})
    hashes: dict[str, str] = {}
    names = [stream["stream_id"] for stream in corpus["streams"]]
    names += [case["case_id"] for case in corpus["generated_cases"]]
    for name in sorted(names):
        bundle: dict[str, Any] = read_sealed(root / name / MANIFEST_NAME, FRAME_BUNDLE)
        identity = bundle["identity"]
        require_bundle_place(name, corpus, bundle["corpus_manifest_sha256"], bundle["stream_id"])
        if bundle_hash(identity) != bundle["bundle_sha256"]:
            raise CorpusRefusal(
                RefusalCode.RECORD_TAMPERED, "bundle index changed during description"
            )
        hashes[name] = bundle["bundle_sha256"]
        bundles.append(bundle)
        for entry in identity["frames"]:
            frames.append(
                {
                    "stream_id": name,
                    "frame_index": entry["frame_index"],
                    "content_frame_index": entry.get("content_frame_index", entry["frame_index"]),
                    "pts": entry["pts"],
                    "sha256": entry["sha256"],
                    "path": f"../../frames/{name}/{frame_name(entry['frame_index'], identity['pixel_format'])}",
                    "width": identity["width"],
                    "height": identity["height"],
                    "pixel_format": identity["pixel_format"],
                    "bytes_per_frame": identity["bytes_per_frame"],
                    "time_base": identity["time_base"],
                    "generated": bundle["generated"] is not None,
                }
            )
    require_frame_set(corpus, hashes, data_root)
    return {"streams": streams, "bundles": bundles, "frames": frames}


def _counts(corpus: dict[str, Any]) -> dict[str, dict[str, int]]:
    result = {}
    for split in ("development", "calibration", "locked"):
        streams = [stream for stream in corpus["streams"] if stream["split"] == split]
        names = {stream["stream_id"] for stream in streams}
        result[split] = {
            "groups": len({stream["group_id"] for stream in streams}),
            "encounters": len({stream["encounter_id"] for stream in streams}),
            "streams": len(streams),
            "generated_cases": sum(
                case["parent_stream_id"] in names for case in corpus["generated_cases"]
            ),
        }
    return result


def _contracts() -> list[dict[str, str]]:
    contracts = load_contract_set()
    names = (
        "declaration/dataset",
        "record/corpus-manifest",
        "record/source-manifest",
        "record/frame-set",
        "record/frame-bundle",
    )
    result = []
    for name in names:
        contract = contracts.named(name)
        version = contract.versions[-1]
        result.append(
            {
                "contract": name,
                "version": version.version,
                "urn": contract.urn(version),
                "sha256": version.file_sha256,
            }
        )
    return result


def _artifacts(
    corpus: dict[str, Any], declaration: dict[str, str], root: Path, public: bool
) -> dict[str, bytes]:
    collected = _records(corpus, root)
    records = public_tables(corpus, collected) if public else collected
    tables = {name: _csv(records[name]) for name in TABLES}
    card = (
        f"# {declaration['title']}\n\n{declaration['description']}\n\n"
        f"Visibility: {'public' if public else 'restricted'}.\n\n"
        "Generated cases are a labelled slice and do not count as encounters. "
        "Selection limits and completeness are not independently verified. "
        "Raw frames are headerless packed rgb24; use the frame-bundle contract and the frame index.\n\n"
        "Split counts (locked contains counts only in public output):\n\n"
        f"```json\n{json.dumps(_counts(corpus), sort_keys=True, indent=2)}\n```\n"
    )
    if public:
        card += (
            "\nPublic tables include only fields frozen as public, for streams outside the locked "
            "split. They carry permitted terms, layout and the frame index. Locked data is counts "
            "only. Identifying text, source hashes and the frame-set bundle list are omitted.\n"
        )
    else:
        card += (
            "\nStreams carry source rights, sensitivity, retention, capture facts and "
            "selection limits.\n"
        )
    output = {f"{name}.csv": payload for name, payload in tables.items()}
    output["croissant.json"] = (
        json.dumps(metadata(declaration, tables), sort_keys=True, indent=2) + "\n"
    ).encode("ascii")
    output["dataset-card.md"] = card.encode("ascii", errors="backslashreplace")
    output["contracts.json"] = (json.dumps(_contracts(), sort_keys=True, indent=2) + "\n").encode(
        "ascii"
    )
    contract_set = load_contract_set()
    contract_root = contract_set.root
    paths = [contract_root / "registry.yaml", contract_root / "README.md"]
    paths.extend(sorted((contract_root / "meta").rglob("*.json")))
    paths.extend(sorted((contract_root / "meta").rglob("*.md")))
    paths.extend(sorted((contract_root / "meta").rglob("*.txt")))
    for contract in contract_set.contracts:
        for version in contract.versions:
            paths.append(
                contract_root / contract.family / contract.contract_id / f"{version.version}.json"
            )
    for path in paths:
        output[f"contracts/{path.relative_to(contract_root).as_posix()}"] = path.read_bytes()
    return output


def describe_corpus(
    corpus_id: str, declaration_path: Path, data_root: Path, visibility: str = "restricted"
) -> DescriptorResult:
    """Verify inputs and write an immutable, deterministic descriptor under the data root."""
    if visibility not in ("public", "restricted"):
        raise invalid("unknown descriptor visibility")
    public = visibility == "public"
    corpus: dict[str, Any] = load_corpus_manifest(corpus_id, data_root)
    if public and corpus["scenario_rights"]["sharing"] != "public":
        raise CorpusRefusal(RefusalCode.RIGHTS_CONFLICT, "public descriptor is not permitted")
    declaration = _declaration(declaration_path, public)
    verify_corpus_frames(corpus_id, data_root)
    output = _artifacts(corpus, declaration, data_root, public)
    parent = data_root / "corpus" / corpus_id / "descriptions"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / visibility
    with tempfile.TemporaryDirectory(prefix=".incoming-", dir=parent) as temp:
        temporary = Path(temp)
        for name, payload in output.items():
            destination = temporary / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        if target.exists():
            found = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
            if found != set(output) or any(
                (target / name).read_bytes() != payload for name, payload in output.items()
            ):
                raise CorpusRefusal(
                    RefusalCode.CORPUS_CONFLICT, "descriptor already exists with different content"
                )
        else:
            os.rename(temporary, target)
    return DescriptorResult(corpus_id, target / "croissant.json")
