"""Corpus provenance: declared sources, canonical decoding and immutable manifests."""

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_frame_bundle
from ss_track.corpus.bundles.frames import FrameBundle, FrameRef
from ss_track.corpus.bundles.stage_report import FramesResult
from ss_track.corpus.bundles.staging import stage_corpus
from ss_track.corpus.bundles.verification import verify_corpus_frames
from ss_track.corpus.hosts.hash_comparison import ComparisonResult, compare_staged_hashes
from ss_track.corpus.hosts.host_hashes import StagedHashesResult, record_staged_hashes
from ss_track.corpus.sources.amendment import amend_source_terms
from ss_track.corpus.sources.importer import ImportResult, import_source
from ss_track.corpus.sources.redecode import redecode_source
from ss_track.corpus.sources.replacement import ReplacementResult
from ss_track.corpus.versions.builder import BuildResult, build_corpus

__all__ = [
    "BuildResult",
    "ComparisonResult",
    "CorpusRefusal",
    "FrameBundle",
    "FrameRef",
    "FramesResult",
    "ImportResult",
    "RefusalCode",
    "ReplacementResult",
    "StagedHashesResult",
    "amend_source_terms",
    "build_corpus",
    "compare_staged_hashes",
    "import_source",
    "open_frame_bundle",
    "record_staged_hashes",
    "redecode_source",
    "stage_corpus",
    "verify_corpus_frames",
]
