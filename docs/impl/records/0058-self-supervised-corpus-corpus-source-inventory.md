# corpus-source-inventory

## Task and scope

- Id / capability: `corpus-source-inventory` / `self-supervised-corpus`
- State: accepted
- Source: plan task, start commit `1b6be0f`; working tree clean.
- Plan counts at start: 107 agent, 23 human; next agent `corpus-source-inventory`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-source-inventory

Operators need to inventory upstream video files and their terms before selecting a combined pool.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A deterministic source inventory identifies videos, provenance, rights
  evidence, acquisition pins and unresolved facts for the two selected collections.
- Scope boundary: Offline fixtures and metadata inspection; no real media download, assumed rights,
  source approval, review or publication.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `contracts/`,
  `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Specify and contract any interchangeable inventory; preserve Zenodo version and
  archive checksum, Hugging Face dataset commit, per-video upstream paths, attribution and terms,
  source and annotation references, known upstream splits, status and exclusions. Record unknown
  provenance and terms explicitly; credentials never enter artifacts.
- Acceptance gates: Network-free fixtures cover both collections, unresolved rights, duplicate paths,
  deterministic output, valid contract examples and refusing a moving or missing revision; `make ci`
  passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

Added `declaration/source-inventory` 1.0.0 for an operator's candidate videos and two minor
`result/command` versions for its counts, location and digest. `corpus/sources/inventory.py`
validates, checks provider pins and cross-field rules, orders the declaration and writes canonical
JSON once; `discover inventory` reports the digest and unresolved fact counts. It never grants
rights, downloads media or checks that a syntactically pinned commit exists. The reader refuses
common credential forms and URL credentials, query strings and fragments without echoing them;
operators must not provide credentials because general secret detection is not possible.

The existing [corpus documentation](../current/corpus.md#source-inventory) states the input, result,
limits and verification. The reader reuses existing schema, canonical JSON and write-once behavior;
no dependency, environment variable or sibling interface changed. Source acquisition remains the
owner of listing pinned upstream metadata and comparing it with an inventory.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Both providers and deterministic inventory | `.venv/bin/pytest -q tests/corpus/sources/test_inventory.py` | pass: 10 tests; offline fixtures, no real media |
| Contract example | `.venv/bin/ss-track contracts validate --file tests/schema/examples/declaration-source-inventory.json --contract declaration/source-inventory` | pass |
| Fixture run and replay | `ss-track discover inventory` on the contract example | pass: `$DATA_DIR/self-supervised-corpus/source-inventory-fixture-20261108/inventory.json`; fixture identities only |
| Required project gate | `make ci` | pass: 2276 passed, 7 skipped |
| Documentation | `make lint-md`, `make lint-doc-links`, `make lint-spec-plan` | pass |

## Audit handoff

- `AUD-corpus-source-inventory-1`: the local inventory reader does not enumerate provider files or
  verify their metadata or commit existence; its information is operator supplied. Owner:
  `corpus-source-acquisition`, whose execution path and fixture gates now state metadata enumeration
  and mismatches.
- Dropped: no sibling repository change is necessary; this inventory reads a local declaration and
  does not invoke ss-video or ss-fusion.
- Fixed: initial output reused discovery-window count fields for source-video counts. It now uses
  purpose-specific fields in `result/command` 1.20.0, tested through the CLI.

## Close or resume

Gates passed. Source acquisition, combined pool and authorization drop the completed inventory
dependency. After completion 106 agent and 23 human tasks remain; the next agent task is
`corpus-source-acquisition` and the next human task is `define-locked-test-policy (optional)`.
The `self-supervised-corpus` capability remains planned.
