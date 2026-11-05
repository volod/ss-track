# Descriptor refresh

## Task and scope

- Id / capability: `descriptor-refresh` / `data-contracts`
- State: accepted.
- Source: plan task; starting commit `7904c46`; working tree clean.
- Plan counts at start: 106 agent, 22 human; next agent `decode-policy-reimport (optional)`, next
  human `select-development-workload`.
- Accepted task:

```markdown
#### descriptor-refresh (optional)

A descriptor directory is immutable. After an operator corrects the title or license, describing the
same corpus and visibility refuses with `CORPUS_CONFLICT` until the old output is removed manually.

- Serves: `data-contracts` -- [Dataset descriptors](../design/spec.md#175-dataset-descriptors-and-self-service)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator can safely regenerate discovery metadata for the same corpus
  without removing the previous descriptor by hand.
- Scope boundary: Local generated descriptions only; sealed evidence and publication stay untouched.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/<id>/descriptions/`.
- Execution path: Provide a deterministic destination per declaration or an atomic replacement with a
  recovery path. Keep public and restricted outputs separate and verify terms before writing.
- Acceptance gates: A corrected declaration produces a usable descriptor, repeats give identical
  bytes, interruption never exposes a mixed descriptor, and a public refresh exposes no restricted
  value or locked per-sequence fact.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none. The execution path allowed either a destination per declaration or an atomic
  replacement. The replacement keeps the published path `descriptions/<visibility>/`.

## Implementation

`corpus describe` still verifies source terms, the frame set and every frame before it writes.
`corpus/descriptor_publish.py` then publishes one visibility. The same bytes leave the directory in
place. Different bytes are written under a scratch directory, the published directory moves to
`.replaced-<visibility>`, and the new tree takes its name. A failure during that second rename puts
the previous tree back. A later run restores a previous tree left beside a missing directory, and
removes one left beside a directory that was already published. A scratch tree is never published.
Public and restricted directories stay separate. The command's recorded JSON is unchanged. The help
text now says that the command writes or replaces a descriptor. No dependency, environment variable
or package metadata changed.

A per-declaration directory was rejected because a consumer would keep reading the previous
generation at the path this command already returns. Sealed records, frame bundles and the other
visibility are not modified. Spec section 17.5 now states the replacement. The command sketch no
longer shows `--out`; the descriptor is a directory on the data root. The
[corpus page](../current/corpus.md#dataset-descriptors) states the operator-visible result.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Corrected declaration, identical repeat, sealed bytes | `.venv/bin/python -m pytest tests/corpus/test_descriptor_refresh.py` | a corrected title and license replace `descriptions/restricted` and leave frame files readable; a repeat keeps the same inode and bytes; corpus files outside `descriptions/` are unchanged; a public request, a missing license and a damaged frame each leave the published tree in place |
| Interrupted swap | `.venv/bin/python -m pytest tests/corpus/test_descriptor_publish.py` | a failed second rename restores the previous file set; a killed swap does not publish a partial scratch tree; a published tree is kept when recovery remains; one visibility does not change the other |
| Public refresh | `.venv/bin/python -m pytest tests/corpus/test_public_descriptor.py` | the corrected public title and license replace the public descriptor; locked identifiers, holders, notes and source hashes stay absent; the restricted directory is not created |
| Repository gate | `make ci` | pass: format, lint, types, complexity, shell lint, doc links, spec-plan, contract history, and 1563 tests |

## Audit handoff

Reviewed the swap, the identical-byte short circuit, refusal-before-write, visibility separation and
the killed-run states.

- `AUD-descriptor-refresh-1`: nonblocking. `descriptor_publish.py` adds a third `flock` and scratch
  clear beside `staging.py` and `amendment.py`. A later merge can miss one of the three. Owner:
  `corpus-provenance-audit`, whose execution path now names `descriptor_publish.py`.

The moment between the two renames, when the published directory is absent, is the swap itself and
needs no further task. A previous restricted generation can sit in `.replaced-restricted` until
removal; it is the same data root as the restricted descriptor, and the next description removes or
restores it. No further task.

## Close or resume

All acceptance gates passed. The task is removed from the plan. The current page
[corpus](../current/corpus.md#dataset-descriptors) states the available behavior. The plan holds
105 agent and 22 human tasks; the next agent task is `decode-policy-reimport (optional)`, and the
next human task is `select-development-workload`. The `data-contracts` capability remains planned
with open work.
