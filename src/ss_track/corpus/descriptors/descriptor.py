"""Export a verified corpus as deterministic, local dataset discovery artifacts."""

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import read_bundle_record, require_bundle_place
from ss_track.corpus.bundles.frame_set import require_frame_set
from ss_track.corpus.bundles.verification import verify_corpus_frames
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.corpus.descriptors.descriptor_metadata import TABLES, metadata
from ss_track.corpus.descriptors.descriptor_public import SPLITS, public_tables
from ss_track.corpus.descriptors.descriptor_publish import publish_descriptor
from ss_track.corpus.descriptors.descriptor_rows import frame_rows
from ss_track.corpus.records.kinds import CORPUS_MANIFEST, FRAME_BUNDLE, FRAME_SET, SOURCE_MANIFEST
from ss_track.corpus.sources.stored import load_source_record
from ss_track.corpus.storage.layout import frames_root
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.registry.contract import Contract
from ss_track.schema.registry.store import (
    META_DIRECTORY,
    README_NAME,
    REGISTRY_NAME,
    ContractSet,
    load_contract_set,
)
from ss_track.schema.validation.enforce import read_declaration

DATASET_CONTRACT = "declaration/dataset"
DATASET_SCHEMA_VERSION = 1
PUBLIC = "public"
RESTRICTED = "restricted"
VISIBILITIES = (RESTRICTED, PUBLIC)
_DATASET_TEXT = ("title", "description", "license", "citation", "address")
_DESCRIBED_RECORDS = (CORPUS_MANIFEST, SOURCE_MANIFEST, FRAME_SET, FRAME_BUNDLE)
_META_SUFFIXES = ("*.json", "*.md", "*.txt")


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
        raw = read_declaration(path, DATASET_CONTRACT, DATASET_SCHEMA_VERSION)
        fields = Fields(raw, "dataset")
        result = {name: fields.text(name) for name in _DATASET_TEXT}
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
    streams: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
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
        bundle = read_bundle_record(root / name)
        require_bundle_place(name, corpus, bundle["corpus_manifest_sha256"], bundle["stream_id"])
        hashes[name] = bundle["bundle_sha256"]
        bundles.append(bundle)
        frames.extend(frame_rows(bundle))
    require_frame_set(corpus, hashes, data_root)
    return {"streams": streams, "bundles": bundles, "frames": frames}


def _counts(corpus: dict[str, Any]) -> dict[str, dict[str, int]]:
    result = {}
    for split in SPLITS:
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


def _contracts(contracts: ContractSet) -> list[dict[str, str]]:
    """List the newest version of each contract a descriptor's values follow, dataset first."""
    by_kind = contracts.records_by_kind()
    described: list[Contract] = [contracts.named(DATASET_CONTRACT)]
    described += [by_kind[record_format.kind] for record_format in _DESCRIBED_RECORDS]
    result = []
    for contract in described:
        version = contract.newest()
        if version is None:
            continue
        result.append(
            {
                "contract": contract.name,
                "version": version.version,
                "urn": contract.urn(version),
                "sha256": version.file_sha256,
            }
        )
    return result


def _contract_files(contracts: ContractSet) -> dict[str, bytes]:
    """Copy the frozen set a consumer needs to read the records without this repository."""
    root = contracts.root
    paths = [root / REGISTRY_NAME, root / README_NAME]
    for suffix in _META_SUFFIXES:
        paths.extend(sorted((root / META_DIRECTORY).rglob(suffix)))
    for contract in contracts.contracts:
        paths.extend(root / contract.relative_path(version) for version in contract.versions)
    return {f"contracts/{path.relative_to(root).as_posix()}": path.read_bytes() for path in paths}


def _artifacts(
    corpus: dict[str, Any], declaration: dict[str, str], root: Path, public: bool
) -> dict[str, bytes]:
    contracts = load_contract_set()
    collected = _records(corpus, root)
    records = public_tables(corpus, collected, contracts) if public else collected
    tables = {name: _csv(records[name]) for name in TABLES}
    card = (
        f"# {declaration['title']}\n\n{declaration['description']}\n\n"
        f"Visibility: {PUBLIC if public else RESTRICTED}.\n\n"
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
    output["contracts.json"] = (
        json.dumps(_contracts(contracts), sort_keys=True, indent=2) + "\n"
    ).encode("ascii")
    return output | _contract_files(contracts)


def describe_corpus(
    corpus_id: str, declaration_path: Path, data_root: Path, visibility: str = RESTRICTED
) -> DescriptorResult:
    """Verify the corpus, then publish one descriptor generation under the data root.

    The same inputs leave the published directory in place. Different generated bytes replace
    that visibility only, and only after this verification has succeeded.
    """
    if visibility not in VISIBILITIES:
        raise invalid("unknown descriptor visibility")
    public = visibility == PUBLIC
    corpus: dict[str, Any] = load_corpus_manifest(corpus_id, data_root)
    if public and corpus["scenario_rights"]["sharing"] != PUBLIC:
        raise CorpusRefusal(RefusalCode.RIGHTS_CONFLICT, "public descriptor is not permitted")
    declaration = _declaration(declaration_path, public)
    verify_corpus_frames(corpus_id, data_root)
    output = _artifacts(corpus, declaration, data_root, public)
    manifest = publish_descriptor(data_root, corpus_id, visibility, output)
    return DescriptorResult(corpus_id, manifest)
