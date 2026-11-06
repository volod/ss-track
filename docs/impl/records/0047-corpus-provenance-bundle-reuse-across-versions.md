# Bundle reuse across versions

## Task and scope

- Id / capability: `bundle-reuse-across-versions` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `7521e71cc27dca8ea3c2f712484e7595ff03a6fc`; clean worktree.
- Plan counts at start: 131 open (108 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=103, HUMAN-GATED=13, RUN NEEDED=5. Next agent `bundle-reuse-across-versions (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### bundle-reuse-across-versions (optional)

A new corpus version that keeps a source decodes and stores identical frames again, though its
`bundle_sha256` is unchanged, so any new version costs hours and terabytes.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` reuses a linked version's frames by hard link when the bundle
  hash matches, and reports which streams it reused.
- Scope boundary: Bundles of the same hash on one data root, inside a declared chain. The new version
  still writes its own bundle record and frame set. A host that cannot link decodes, and nothing is
  shared across decode policies.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Predict the bundle hash from the sealed index and the source and policy hashes before
  decoding, verify every frame hash of the candidate, then link and write the record.
- Acceptance gates: A kept source gives the same `bundle_sha256` and identical bytes as a fresh stage,
  with no decode and no added frame storage. A damaged candidate is refused by name and never linked.
  A stream with another window or policy decodes. Removing one version leaves the other readable.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus stage` predicts a bundle hash from the sealed index and the current source and policy
before it decodes. A match in the declared chain, nearest first, is checked frame by frame and
hard-linked. The new version writes its own bundle record and frame set. The command stays
`staged`. Each reused bundle reports `reused` and `reused_from`. A repeat reports `unchanged`
and omits the origin.

`reuse_offers.py` lists candidates. `reuse.py` matches, checks and links them. `bundle_record.py`
builds the identity a fresh decode and a reuse both seal. `frame_store.linked_name` reports a
host that cannot link, and that stream is decoded. A damaged candidate is `FRAME_CORRUPTED` and
names both streams. A damaged stored source is `SOURCE_HASH_MISMATCH` before any link. A case is
not reused from another version; a case of a reused parent is still written.

`result/command` 1.13.0 adds `reused` and optional `reused_from`. No new dependency, environment
variable, refusal code or manifest field. Current page:
[Reusing a linked version](../current/corpus.md#reusing-a-linked-version). Specification section
4.1 states the reuse.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A kept source matches a fresh stage, with no decode and no added frame storage | `tests/corpus/bundles/test_bundle_reuse.py::test_a_kept_source_reuses_frames_without_decoding_or_storing_them` | pass; same `bundle_sha256` and bytes, shared inodes with the linked version, disjoint from the fresh stage, and the command result matches `result/command` 1.13.0 |
| A damaged candidate is refused by name and never linked | `tests/corpus/bundles/test_bundle_reuse.py::test_a_damaged_candidate_is_refused_by_name_and_not_linked` | pass; `FRAME_CORRUPTED` names the stream and the candidate, the new bundle is absent, and the candidate link count stays 1 |
| Another window or policy decodes | `tests/corpus/bundles/test_bundle_reuse_bounds.py::test_another_window_decodes` and `test_another_policy_decodes` | pass; each decodes once and reports `staged` |
| Removing one version leaves the other readable | `tests/corpus/bundles/test_bundle_reuse.py::test_removing_one_version_leaves_the_other_readable` | pass; each survivor verifies, and the shared frame stays mode `0444` |
| A host that cannot link decodes | `tests/corpus/bundles/test_bundle_reuse.py::test_a_host_that_cannot_link_decodes` | pass; `os.link` raising `EXDEV` decodes once, with disjoint inodes and the same bundle hash |
| `make ci` | `make ci` | pass; 1897 tests |

## Audit handoff

`none identified` for new work. Reviewed the reuse path, the stage report, the command contract
and the tests above.

Dropped, each because it needs no work:

- Damage of a shared inode is visible from every version that links it. Section 4.1 and the
  current page state that removing one name leaves the other. The same limit is accepted for a
  case frame in record 0039.
- A damaged nearest candidate is refused, and an older intact copy is not tried. The refusal
  names that bundle. The current page states the operator removes or repairs it, then stages
  again. An older copy is then a candidate.
- The check of a frame and the link of that frame are two calls. A change in between is the same
  gap record 0039 accepts for a case frame. The next `corpus verify` names it.

## Close or resume

Gates passed. Current page, specification section 4.1,
the capability evaluation, contracts page, data-contracts note, test plan, records index and the
plan are updated. Plan counts after: 130 open (107 agent, 23 human). Statuses: BLOCKED BY
HUMAN=10, CLEAR=102, HUMAN-GATED=13, RUN NEEDED=5. Next agent
`near-duplicates-outside-the-chain (optional)`; next human `define-locked-test-policy (optional)`.
`corpus-provenance` stays `planned`.
