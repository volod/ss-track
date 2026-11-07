"""Typed form of an operator's discovery plan, read under its contract.

The contract requires the owner's source approval on every plan: ss-track cannot tell fixture media
from real sources, so a run over real sources cannot be written without one. Hint file paths are
relative to the plan, so a plan and its hint files move together.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.schema.validation.enforce import read_declaration

PLAN_CONTRACT = "declaration/discovery-plan"
PLAN_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExtractorPlan:
    """One pinned extractor, which runs in its own worker process."""

    kind: str
    extractor_id: str
    model: str
    pretrained: str | None
    device: str
    batch_size: int
    dimensions: int
    weights: tuple[dict[str, Any], ...]

    def to_worker(self) -> dict[str, Any]:
        """Return what the worker is told about the extractor it loads."""
        return {
            "kind": self.kind,
            "extractor_id": self.extractor_id,
            "model": self.model,
            "pretrained": self.pretrained,
            "device": self.device,
            "batch_size": self.batch_size,
            "dimensions": self.dimensions,
        }


@dataclass(frozen=True, slots=True)
class EmbeddingPlan:
    """The pinned package, the frames to embed and each extractor."""

    package_name: str
    package_commit: str
    frame_stride: int
    extractors: tuple[ExtractorPlan, ...]


@dataclass(frozen=True, slots=True)
class HintFile:
    """One ss-video hint file the run maps onto staged frames."""

    hint_source_id: str
    path: Path


@dataclass(frozen=True, slots=True)
class DiscoveryPlan:
    """One validated discovery plan."""

    run_id: str
    corpus_id: str
    approval_owner: str
    approval_reference: str
    window_frames: int
    audit_seed: int
    audit_sample_size: int
    embedding: EmbeddingPlan | None
    hints: tuple[HintFile, ...]


def _weight(fields: Fields) -> dict[str, Any]:
    return {
        "name": fields.text("name"),
        "revision": fields.text("revision"),
        "sha256": fields.text("sha256"),
        "size_bytes": fields.index("size_bytes"),
    }


def _extractor(raw: object, where: str) -> ExtractorPlan:
    fields = Fields(raw, where)
    weights = tuple(
        _weight(Fields(item, f"{where}.weights[{position}]"))
        for position, item in enumerate(fields.items("weights"))
    )
    _require_ascending([weight["name"] for weight in weights], f"{where}.weights", "name")
    return ExtractorPlan(
        kind=fields.text("kind"),
        extractor_id=fields.text("extractor_id"),
        model=fields.text("model"),
        pretrained=fields.optional_text("pretrained"),
        device=fields.text("device"),
        batch_size=fields.index("batch_size"),
        dimensions=fields.index("dimensions"),
        weights=weights,
    )


def _require_ascending(values: list[Any], where: str, key: str) -> None:
    """The `order` rule: each list is ascending by its id, each id once."""
    if any(not values[index - 1] < values[index] for index in range(1, len(values))):
        raise invalid(f"{where} must be in ascending {key} order, each {key} once")


def _embedding(fields: Fields) -> EmbeddingPlan | None:
    if not fields.has("embedding"):
        return None
    embedding = fields.child("embedding")
    package = embedding.child("package")
    extractors = tuple(
        _extractor(raw, f"{embedding.where}.extractors[{position}]")
        for position, raw in enumerate(embedding.items("extractors"))
    )
    ids = [extractor.extractor_id for extractor in extractors]
    _require_ascending(ids, f"{embedding.where}.extractors", "extractor_id")
    return EmbeddingPlan(
        package_name=package.text("name"),
        package_commit=package.text("commit"),
        frame_stride=embedding.index("frame_stride"),
        extractors=extractors,
    )


def read_discovery_plan(path: Path) -> DiscoveryPlan:
    """Read and validate one discovery plan."""
    fields = Fields(read_declaration(path, PLAN_CONTRACT, PLAN_SCHEMA_VERSION), "plan")
    approval = fields.child("source_approval")
    audit = fields.child("audit")
    hints = tuple(
        HintFile(item.text("hint_source_id"), path.resolve().parent / item.text("file"))
        for item in (
            Fields(raw, f"plan.hints[{position}]")
            for position, raw in enumerate(fields.optional_items("hints"))
        )
    )
    _require_ascending([hint.hint_source_id for hint in hints], "plan.hints", "hint_source_id")
    return DiscoveryPlan(
        run_id=fields.text("run_id"),
        corpus_id=fields.text("corpus_id"),
        approval_owner=approval.text("owner"),
        approval_reference=approval.text("reference"),
        window_frames=fields.child("pool").index("window_frames"),
        audit_seed=audit.index("seed"),
        audit_sample_size=audit.index("sample_size"),
        embedding=_embedding(fields),
        hints=hints,
    )
