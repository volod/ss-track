"""Each sealed record format: the kind it stamps and the one major this code reads and writes.

They sit apart from the writers so that the read path, the writers and the refusals name a format
by one value, and a format change has one place to go: a new major is one edit below, which a test
holds to the newest frozen contract of that kind.
"""

from ss_track.core.evidence.format import RecordFormat

SOURCE_MANIFEST_KIND = "ss-track.source-manifest"
CORPUS_MANIFEST_KIND = "ss-track.corpus-manifest"
FRAME_BUNDLE_KIND = "ss-track.frame-bundle"
FRAME_SET_KIND = "ss-track.frame-set"
STAGED_HASHES_KIND = "ss-track.staged-hashes"
HASH_COMPARISON_KIND = "ss-track.hash-comparison"
DISCOVERY_RUN_KIND = "ss-track.discovery-run"
CANDIDATE_INVENTORY_KIND = "ss-track.candidate-inventory"
FEATURE_ROWS_KIND = "ss-track.feature-rows"
CORPUS_LINKS_KIND = "ss-track.corpus-links"
CORPUS_FREEZE_KIND = "ss-track.corpus-freeze"
SOURCE_ACQUISITION_KIND = "ss-track.source-acquisition"
CORPUS_POOL_KIND = "ss-track.corpus-pool"
AUDIT_BLINDING_KIND = "ss-track.audit-blinding"
LINK_REVIEW_HANDOFF_KIND = "ss-track.link-review-handoff"


SOURCE_MANIFEST = RecordFormat(SOURCE_MANIFEST_KIND, major=3)
CORPUS_MANIFEST = RecordFormat(CORPUS_MANIFEST_KIND, major=3)
FRAME_BUNDLE = RecordFormat(FRAME_BUNDLE_KIND, major=3)
FRAME_SET = RecordFormat(FRAME_SET_KIND, major=1)
STAGED_HASHES = RecordFormat(STAGED_HASHES_KIND, major=1)
HASH_COMPARISON = RecordFormat(HASH_COMPARISON_KIND, major=1)  # written; no command reads it back
DISCOVERY_RUN = RecordFormat(DISCOVERY_RUN_KIND, major=1)
CANDIDATE_INVENTORY = RecordFormat(CANDIDATE_INVENTORY_KIND, major=1)
FEATURE_ROWS = RecordFormat(FEATURE_ROWS_KIND, major=1)
CORPUS_LINKS = RecordFormat(CORPUS_LINKS_KIND, major=1)
CORPUS_FREEZE = RecordFormat(CORPUS_FREEZE_KIND, major=1)
SOURCE_ACQUISITION = RecordFormat(SOURCE_ACQUISITION_KIND, major=1)
CORPUS_POOL = RecordFormat(CORPUS_POOL_KIND, major=1)
AUDIT_BLINDING = RecordFormat(AUDIT_BLINDING_KIND, major=1)
LINK_REVIEW_HANDOFF = RecordFormat(LINK_REVIEW_HANDOFF_KIND, major=1)
