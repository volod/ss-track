# Shared evidence primitives

## Task and scope

- Id / capability: `shared-evidence-primitives` / `corpus-provenance`
- State: accepted
- Source: plan task; working tree clean at start.
- Plan counts at start: 136 agent, 28 human; next agent `shared-evidence-primitives`, next human
  `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### shared-evidence-primitives

Sealed records, atomic writes, locks and the clean-kind registry live inside the corpus package,
and its record reader imports a source module. Labels, run bundles, host profiles and trials need
the same primitives, and each would otherwise copy them or import corpus internals.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Every area seals, reads, locks and cleans evidence through one shared
  package, and no area imports a corpus module to do so.
- Scope boundary: A move of the sealing and sealed-read path, the read window, atomic scratch
  writes, locks and the clean-kind registry. Corpus-specific kinds, layout and projections stay in
  the corpus area and register themselves. The one term the read path takes from a source module
  becomes a value its caller supplies. No sealed byte, hash, refusal code or contract moves.
- Data and artifact paths: `src/ss_track/core/`, `src/ss_track/corpus/records/`,
  `src/ss_track/corpus/storage/`, `tests/core/`, `tests/corpus/`, `AGENTS.md`,
  `docs/guide/planning-workflow.md`.
- Execution path: Move the primitives under unchanged function names where possible, let each area
  register its record kinds and clean kinds, and add an import-boundary test. Update the clean-kind
  path that `AGENTS.md` and the planning workflow name.
- Acceptance gates: Every sealed fixture and historic record reads to the same bytes and hashes. An
  import-boundary test fails when the shared package imports an area, or when a module outside the
  corpus area imports it for sealing, locking or cleaning. `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

Moved sealing, reads, read windows, refusals, format primitives, scratch, locks and cleaning to
`core`. Corpus owns its formats, projections, historic shapes and clean-kind definitions, and
registers those with shared registries. The source terms command is supplied to the historic shape.
Registered the evidence package in the wheel. Contracts, serialized bytes, hashes, refusal codes,
CLI and dependencies are unchanged. See [Corpus](../current/corpus.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Historic records and sealed fixtures | `make ci` | Passed, including historic records, sealed read and installed-wheel tests. |
| Import boundary | `tests/core/test_evidence_boundaries.py` via `make ci` | Passed; scans shared and non-corpus modules, including relative imports. |
| Full required gate | `make ci` | Passed; 2383 tests passed, 112 deselected. |

## Audit handoff

None identified. Reviewed shared imports, area registrations, clean kinds, package inclusion,
historic read paths, documentation references and dependent plan tasks. Duplicate projections and
clean kinds are rejected instead of silently replacing registrations.

## Close or resume

Accepted after the required gate. Current corpus and contracts pages and authoring guidance updated;
plan scope removed and dependencies adjusted. Plan counts after: 135 agent and 28 human; capability
remains shipped.
