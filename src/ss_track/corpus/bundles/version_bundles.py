"""The bundles of one corpus version as stage and verify meet them.

Both read the version's streams and cases, refuse it when its source terms no longer hold, and
open each case against the parent frames staged beside it.
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.sources.stored import require_source_record
from ss_track.corpus.sources.terms import require_retention

type Manifest = dict[str, Any]
type OpenBundle = Callable[[str], FrameBundle]


def declared_streams(corpus: Manifest) -> list[dict[str, Any]]:
    """Return the streams a corpus version declares, in its sealed order."""
    streams: list[dict[str, Any]] = corpus["streams"]
    return streams


def declared_cases(corpus: Manifest) -> list[dict[str, Any]]:
    """Return the generated cases a corpus version declares, in `case_id` order."""
    cases: list[dict[str, Any]] = corpus["generated_cases"]
    return cases


def require_sources_hold(corpus: Manifest, data_root: Path, today: date) -> None:
    """Refuse a corpus outside its recorded terms, before any bundle is written, skipped or hashed.

    Retention goes first because it reads only the corpus, so removing expired material, which is
    the operator's to do, cannot turn the reason into a missing record. A generated case holds its
    parent's rights, so checking every stream covers every case.
    """
    for stream in declared_streams(corpus):
        require_retention(stream, today)
    for stream in declared_streams(corpus):
        require_source_record(stream, data_root)


class ParentBundle:
    """The parent bundle of the case at hand, opened again only when the parent changes.

    Cases run in `case_id` order, which keeps a parent's cases together whenever their names share
    its prefix, and holding one parent keeps memory to one frame index.
    """

    def __init__(self, corpus: Manifest, root: Path) -> None:
        self._corpus = corpus
        self._root = root
        self._held: FrameBundle | None = None

    def __call__(self, stream_id: str) -> FrameBundle:
        if self._held is None or self._held.stream_id != stream_id:
            self._held = open_corpus_bundle(stream_id, self._corpus, self._root)
        return self._held


def open_case(
    case: dict[str, Any], corpus: Manifest, root: Path, parent_of: OpenBundle
) -> FrameBundle:
    """Open one case's bundle, which must derive from the parent frames staged here now."""
    bundle = open_corpus_bundle(case["case_id"], corpus, root)
    parent = parent_of(case["parent_stream_id"])
    if bundle.parent_bundle_sha256 != parent.bundle_sha256:
        raise CorpusRefusal(
            RefusalCode.BUNDLE_CONFLICT,
            "this generated case derives from frames other than its parent's",
            {
                "stream_id": case["case_id"],
                "parent_stream_id": case["parent_stream_id"],
                "case_parent_bundle_sha256": bundle.parent_bundle_sha256,
                "parent_bundle_sha256": parent.bundle_sha256,
            },
        )
    return bundle
