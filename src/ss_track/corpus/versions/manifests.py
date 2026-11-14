"""Reading a built corpus version: as evidence, or through its major's comparison projection.

Every command after `corpus build` names a version by its identifier, so the identifier is checked
here once, and a name that cannot be a version or has no manifest is `CORPUS_NOT_BUILT`.
"""

from pathlib import Path

from ss_track.core.evidence.sealed import read_comparable, read_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.records.projections import Unprojected
from ss_track.corpus.storage.layout import corpus_manifest_path
from ss_track.corpus.versions.predecessors import Predecessor
from ss_track.schema.validation.enforce import is_shared_type


def load_corpus_manifest(corpus_id: str, data_root: Path) -> dict[str, JsonValue]:
    """Read one built corpus version as evidence, refusing an identifier that cannot name one."""
    return read_sealed(built_manifest_path(corpus_id, data_root), CORPUS_MANIFEST)


def load_predecessor(corpus_id: str, data_root: Path) -> Predecessor:
    """Read a declared predecessor of any major through its projection, for the comparison rules."""
    found = read_comparable(built_manifest_path(corpus_id, data_root), CORPUS_MANIFEST)
    if found.projected is None:
        return Unprojected(corpus_id, found.seal)
    return found.projected


def built_manifest_path(corpus_id: str, data_root: Path) -> Path:
    """Return a built version's manifest, refusing a name that cannot be one or has none."""
    path = corpus_manifest_path(data_root, corpus_id)
    if not is_shared_type("identifier", corpus_id) or not path.is_file():
        raise CorpusRefusal(
            RefusalCode.CORPUS_NOT_BUILT, "no such corpus version", {"corpus_id": corpus_id}
        )
    return path
