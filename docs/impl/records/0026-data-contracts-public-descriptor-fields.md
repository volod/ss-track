# Public descriptor fields

## Task and scope

- Id / capability: `public-descriptor-fields` / `data-contracts`
- State: accepted.
- Source: plan task; starting commit `5f7222b`; working tree clean.
- Plan counts at start: 107 agent, 22 human; next agent `decode-policy-reimport`, next human
  `select-development-workload`.
- Accepted task:

```markdown
#### public-descriptor-fields (optional)

A public corpus description currently has empty record tables: the frozen corpus, source and bundle
contracts have no fields marked public, and the frame-set bundle list is restricted. A consumer can
see counts but cannot discover non-locked streams or their permitted terms from the descriptor.

- Serves: `data-contracts` -- [Dataset descriptors](../design/spec.md#175-dataset-descriptors-and-self-service)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Public descriptors contain only reviewed public facts that help a consumer
  judge and load non-locked data, while locked data remains counts only.
- Scope boundary: Review the existing frozen contracts and make new compatible versions or major
  transitions as warranted; never relax a frozen restriction in place or infer publication rights.
- Data and artifact paths: `contracts/record/`, `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Review each candidate field and its nested sensitivity, freeze justified annotations,
  and project the resulting explicitly public fields into the exporter; retain fail-closed handling for
  everything else. The restricted frame-set bundle list itself must not be disclosed.
- Acceptance gates: A public fixture with non-locked and locked streams exposes only values explicitly
  marked public, includes no restricted or sensitive value, and keeps locked data to counts. An
  unmarked added field stays absent. The separate Croissant validator loads the resulting records.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`record/corpus-manifest` 3.1.0, `record/source-manifest` 2.1.0 and `record/frame-bundle` 3.1.0 add
`x-sensitivity` and change nothing else except `$id`. `schema_version` stays the major, so sealed
bytes stay valid. `record/frame-set` 1.0.0 is unchanged and its bundle list stays restricted.

A field is public when a consumer needs it to judge terms or load non-locked frames: identity,
split, group and encounter, permitted terms, layout, the frame index, frame content hashes, and
scalar recipe parameters that are not coordinates. Holder, notes, free-text retention, capture and
capture-clock evidence are sensitive. Source names and source, manifest and bundle hashes are
restricted, as is the source timestamp array. A restricted or sensitive node hides its children.
Unmarked fields stay absent, including whether a hash was declared, decoder version strings, image
regions and label geometry. `schema/disclosure.py` applies that rule. `corpus/descriptor_public.py`
drops locked streams and cases derived from them before projection, then rebuilds frame rows from
what survived. The full records are still verified before the public view is written.

The [corpus page](../current/corpus.md#dataset-descriptors) states the consumer-visible result. The
[contracts page](../current/contracts.md) lists the new minors. Spec section 17.5 states that an
unmarked field stays absent, a restricted or sensitive ancestor hides its children, and the
frame-set bundle list is not part of a public descriptor.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Public and locked values | `.venv/bin/python -m pytest tests/corpus/test_public_descriptor.py tests/corpus/test_descriptor.py tests/schema/test_disclosure.py` | mixed fixture keeps open terms, blur radius and frame paths; locked ids, holders, notes, cameras, source hashes and frame-set bundle hashes are absent; unmarked fields are absent; a locked-only public view stays counts only |
| Croissant validator | same public-descriptor test, `mlcroissant` 1.1.1 already installed | loads non-empty `streams-records` and `frames-records`; the extra is not a runtime dependency |
| Annotation-only minors | compared 3.0.0/2.0.0 with 3.1.0/2.1.0 after removing `x-sensitivity` and `$id` | the remaining documents are equal |
| Repository gate | `make ci` | pass: format, lint, types, complexity, shell lint, doc links, spec-plan, contract history, and 1555 tests |

The first `make ci` failed four read-window tests. Their synthetic next major was copied from
`3.0.0`, so it dropped the new annotations and the disposition floor treated that as a judgment
change. `tests/corpus/_next_major.py` and `tests/schema/test_dispositions.py` now start from the
newest minor of major 3. The rerun passed.

## Audit handoff

Reviewed integrity, repetition, patterns, naming, cost, gaps and operator-facing ideas for this
projection.

- Image regions, label geometry and coordinate recipe objects stay unmarked on purpose. Spec 17.5
  states that boundary. No further task: publishing them would locate content in the frame.
- Stream, group and encounter identifiers are public because they are how a consumer loads the
  non-locked data. An identifier that is itself a personal name is an operator choice, not a
  projection gap.
- Copied contracts name fields and their marks. They do not carry sealed values, and the frame-set
  bundle list is not copied. No further task.
- `plate_frame` and the other reviewed scalar recipe parameters are public; they are not
  coordinates. No further task.
- Regeneration after a declaration change stays with `descriptor-refresh`, whose text already
  requires a public refresh to expose no restricted value or locked per-sequence fact.

No new plan task.

## Close or resume

All acceptance gates passed. The task is removed from the plan. Current pages
[corpus](../current/corpus.md#dataset-descriptors) and [contracts](../current/contracts.md) state
the available behavior. The plan holds 106 agent and 22 human tasks; the next agent task is
`decode-policy-reimport (optional)`, and the next human task is `select-development-workload`.
The `data-contracts` capability remains planned with open work.
