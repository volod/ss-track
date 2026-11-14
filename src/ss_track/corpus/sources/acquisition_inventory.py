"""Join an operator inventory to enumerated upstream video paths."""

from typing import Any

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.sources.provider_metadata import is_video


def select(collection: dict[str, Any], selection: list[str], authorized: bool) -> None:
    """Require explicit operator authorization and known per-video terms evidence."""
    if not authorized or not selection or len(set(selection)) != len(selection):
        raise invalid("an authorized, nonempty, unique selection is required")
    entries = {item["path"]: item for item in collection["videos"]}
    for path in selection:
        item = entries.get(path)
        if (
            item is None
            or item["status"] != "candidate"
            or item["terms"] is None
            or item["terms_reference"] is None
            or item["attribution"] is None
        ):
            raise CorpusRefusal(
                RefusalCode.RIGHTS_CONFLICT, "selection has unresolved rights or is not a candidate"
            )


def populate(collection: dict[str, Any], paths: set[str]) -> None:
    """Add newly enumerated video paths as unknown; refuse declared paths missing upstream."""
    videos = {path for path in paths if is_video(path)}
    declared = {item["path"] for item in collection["videos"]}
    if not declared.issubset(videos):
        raise CorpusRefusal(
            RefusalCode.SOURCE_DAMAGED, "inventory video paths do not match provider metadata"
        )
    for path in sorted(videos - declared):
        collection["videos"].append(
            {
                "path": path,
                "source_reference": None,
                "annotation_reference": None,
                "upstream_split": None,
                "attribution": None,
                "terms": None,
                "terms_reference": None,
                "status": "unknown",
                "exclusion_reason": None,
            }
        )
    collection["videos"].sort(key=lambda item: item["path"])
