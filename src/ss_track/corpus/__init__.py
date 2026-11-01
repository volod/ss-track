"""Corpus provenance: declared sources, canonical decoding and immutable manifests."""

from ss_track.corpus.builder import BuildResult, build_corpus
from ss_track.corpus.frames import FrameBundle, FrameRef, open_frame_bundle
from ss_track.corpus.hash_comparison import ComparisonResult, compare_staged_hashes
from ss_track.corpus.host_hashes import StagedHashesResult, record_staged_hashes
from ss_track.corpus.importer import ImportResult, import_source
from ss_track.corpus.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.staging import FramesResult, stage_corpus, verify_corpus_frames

__all__ = [
    "BuildResult",
    "ComparisonResult",
    "CorpusRefusal",
    "FrameBundle",
    "FrameRef",
    "FramesResult",
    "ImportResult",
    "RefusalCode",
    "StagedHashesResult",
    "build_corpus",
    "compare_staged_hashes",
    "import_source",
    "open_frame_bundle",
    "record_staged_hashes",
    "stage_corpus",
    "verify_corpus_frames",
]
