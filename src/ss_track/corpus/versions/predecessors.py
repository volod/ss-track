"""The chain of versions a corpus version declares it supersedes, read link by pinned link.

Each link pins the older version's seal, so a replaced version is refused and no loop can form. A
version whose major keeps no projection ends the chain, because its own link cannot be read.
`corpus.versions.lineage` judges what a new version owes the chain.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.projections import SUPERSEDES_FIELD, Unprojected

type Manifest = Mapping[str, Any]
type Predecessor = Manifest | Unprojected
type ManifestLoader = Callable[[str], Predecessor]


def read_predecessors(supersedes: str | None, load: ManifestLoader) -> list[Predecessor]:
    """Return the named version and every version linked behind it, nearest first."""
    if supersedes is None:
        return []
    nearest = load(supersedes)
    if isinstance(nearest, Unprojected):
        return [nearest]
    return [nearest, *follow_links(nearest, load)]


def follow_links(version: Manifest, load: ManifestLoader) -> Iterator[Predecessor]:
    """Yield the versions linked behind one, nearest first.

    Each link pins the older version's seal, so a replaced version is refused, and a loop is
    impossible because it would need a manifest to contain its own hash. Yielding one at a time
    lets a caller keep what it reached when a version further back is gone. A version with no
    projection ends the chain, as its own link cannot be read.
    """
    while (link := version.get(SUPERSEDES_FIELD)) is not None:
        older = load(link["corpus_id"])
        found = predecessor_identity(older)[1]
        if found != link["manifest_sha256"]:
            raise CorpusRefusal(
                RefusalCode.CORPUS_CONFLICT,
                "a superseded version differs from the one its successor pinned",
                {
                    "corpus_id": link["corpus_id"],
                    "successor_corpus_id": version["corpus_id"],
                    "pinned_manifest_sha256": link["manifest_sha256"],
                    "manifest_sha256": found,
                },
            )
        yield older
        if isinstance(older, Unprojected):
            return
        version = older


def link_field(predecessors: Sequence[Predecessor]) -> dict[str, JsonValue]:
    """Return the sealed link, or nothing, so a version naming none keeps its hash."""
    if not predecessors:
        return {}
    corpus_id, manifest_sha256 = predecessor_identity(predecessors[0])
    return {SUPERSEDES_FIELD: {"corpus_id": corpus_id, "manifest_sha256": manifest_sha256}}


def projected(predecessors: Sequence[Predecessor]) -> list[Manifest]:
    """Return the predecessors a comparison can read, nearest first."""
    return [version for version in predecessors if not isinstance(version, Unprojected)]


def predecessor_identity(version: Predecessor) -> tuple[str, str]:
    """Return a predecessor's name and seal, which every major states."""
    if isinstance(version, Unprojected):
        return version.corpus_id, version.manifest_sha256
    return str(version["corpus_id"]), str(version[SEAL_FIELD])
