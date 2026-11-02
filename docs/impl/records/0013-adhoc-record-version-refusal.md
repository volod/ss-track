# Record version refusal

## Task and scope

- Id / capability: `record-version-refusal` / `data-contracts`
- State: accepted
- Source: owner request at `e02a81d`, on the uncommitted work of record 0012: investigate the statement
  that `require_schema` refuses every earlier record against section 15, and suggest specification and
  plan changes by best practice.
- Plan counts at start: 108 tasks (86 agent, 22 human). Next agent: `source-terms-amendment`; next
  human: `select-development-workload`.
- Accepted task: ad hoc, with no plan block.
- Amendments: none.

## Implementation

This change writes no production code. It corrects an earlier claim, adds `#### Reading older records`
under specification section 17.4, and changes the plan. No scope lock was taken, because the output is
documentation across `docs/`.

**Correction.** Record 0012's first audit item and the earlier design text said the refusal contradicts
section 15. That was wrong as worded. Section 15 speaks of run artifacts, and none exist. The refusal
is deliberate, recorded in records 0003, 0004 and 0006, and it stopped an old manifest failing on a
missing key. The statement that every earlier record is refused is true and was reproduced. Record 0012
stays as closed, and this record supersedes that item.

**Root cause.** One exact integer answers whether a tool can parse a record, whether it may serve as
evidence, and what changed, so every change gets one response. Reading and checking are two calls that
can be separated, and nothing classifies a change when it is made.

Plan changes: new `record-read-gate` (required) and `bundle-reuse-across-versions` (optional).
`record-read-window` moves from optional to required and is rewritten around `view`, `facts` and
`retired`. Amended: `corpus-contract-baseline`, `contract-evolution-gate`,
`contract-enforced-readers`, `source-terms-amendment` and `unlinked-version-report`.

Two alternatives were rejected. Accepting older majors with defaults would invent rights, which record
0006 refused. Rewriting records to the new major would change every seal and pin. Upcasting at read is
the established alternative, and copying to a successor stays the last resort for missing facts.

## Acceptance evidence

One-off scripts, not kept. Each era's records were written by that commit's own code, exported with
`git archive`, from one generated FFV1 clip. Readers were `e02a81d` and `357eec4`, the last commit
under decode policy revision 2, so a schema refusal could be told from a policy one.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Older records are refused | `corpus stage`, `verify`, `hashes` and `build` at `e02a81d` on records of `294535c`, `78db68c` and `d6b704d` | Confirmed: `RECORD_SCHEMA_UNSUPPORTED`, exit 1 |
| What each bump changed | JSON key-path diff of real source, corpus and bundle records | Three of five needed no refusal, two did, and source terms entered schema 3 corpus manifests with no bump |
| Re-import over an older source | `import` of a schema 2 declaration on each older era | `IMPORT_CONFLICT`, not a schema refusal |
| Sealed reads without a check | `grep` of `read_sealed` and `require_schema` | 9 reads, 5 checks. Unchecked: `generated.py:117`, `builder.py:276`, `host_hashes.py:79`, `importer.py:179`. No misread was shown, and `host_hashes.py:79` runs after a verify |
| Split guard across a major | At `e02a81d`, a built corpus resealed to schema 2, and the same source declared in `locked` | With `supersedes`: `RECORD_SCHEMA_UNSUPPORTED`. Without it: `built`, `no_lineage`, then `staged`. Control at the current major: `SPLIT_LEAKAGE`. The major was simulated by reseal |
| Predecessor bundle of another major | `corpus stage` of a linked successor | `RECORD_SCHEMA_UNSUPPORTED`, where section 4.1 says a predecessor that cannot be compared is reported |
| Cost of a new version | Same source staged under a new corpus version at `357eec4` | `bundle_sha256` `7bea7105b3` equal across all four eras. Corpus seal, frame set and bundle seal differ, and frames stored twice: 226011 bytes each |
| An in-memory view works | A real bundle given its major 2 shape, read by `357eec4` and by a copy with a four-line view | Exact check refused. View gave `verified`, frame set `5c5e7c97a5` unchanged, file bytes unchanged. One format and one command only |
| Nothing has been lost | `find .data -name manifest.json` | 0 on this data root. Other hosts were not checked |
| Plan and spec agree | `make quality`, which runs the CI checks, coverage, Markdown lint and a package build | Pass: exit 0, 0 spec-plan findings, 0 broken links |

Best-practice sources are linked in the [design](../../design/data-contracts.md#reading-older-records).
The SQLite, TUF and OCI text was read directly. Event sourcing, Schema Registry, Kubebuilder, ext4 and
the Arrow and Parquet items rest on search summaries of those pages.

## Audit handoff

- `AUD-record-version-refusal-1`: a dropped `supersedes` still passes a leak with only `no_lineage`,
  for any unlinked version and not only across majors. `record-read-window` removes the forced route,
  and `unlinked-version-report` stays the only listing, and it is optional. Owner:
  `unlinked-version-report`, by the owner's priority.
- `AUD-record-version-refusal-2`: four sealed reads have no check. Owner: `record-read-gate`.
- `AUD-record-version-refusal-3`: `terms.py` holds a version check by key. Owner:
  `contract-enforced-readers`.
- `AUD-record-version-refusal-4`: an older source's only exit deletes its stored bytes. Owner:
  `source-terms-amendment`.

## Close or resume

Every documentation gate passed, as the table states. Plan after this change: 110 tasks (88 agent, 22
human). `data-contracts` stays `planned`. Nothing was committed.
