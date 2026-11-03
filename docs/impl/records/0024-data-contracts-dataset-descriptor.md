# Dataset descriptor

## Task and scope

- Id / capability: `dataset-descriptor` / `data-contracts`
- State: accepted.
- Source: plan task; starting commit `e4db2ab`; working tree clean.
- Plan counts at start: 107 agent, 22 human; next agent `decode-policy-reimport`, next human
  `select-development-workload`.
- Accepted task:

```markdown
#### dataset-descriptor (optional)

A future consumer cannot find, judge or load a corpus version without this repository.

- Serves: `data-contracts` -- [Dataset
  descriptors](../design/spec.md#175-dataset-descriptors-and-self-service)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track corpus describe` writes a Croissant 1.1 document, a dataset card and
  the contract versions used.
- Scope boundary: Inputs are sealed records, frozen contracts and one `declaration/dataset` supplying
  title, description, license, citation, address and publication date, which no sealed record holds.
  Default visibility is restricted. Raw frames are indexed with their layout. No upload, hosting or
  publication decision.
- Data and artifact paths: `src/ss_track/corpus/`, `contracts/declaration/`, `tests/corpus/`.
- Execution path: Generate from the corpus manifest, frame set and source manifests. Validate with
  `mlcroissant` in a separate locked extra and CI job, outside the runtime closure.
- Acceptance gates: A descriptor validates with zero errors and its streams, bundles and per-frame
  index load as records. Two runs give identical bytes. A public request on a restricted corpus
  refuses without printing a value, and so does one with no license. A public descriptor holds no
  value marked `restricted` or `sensitive` and gives `locked` as counts. Generated cases stay a
  labelled slice.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: the open task now calls out the existing contract sensitivity annotations, so a
  public export must account for them explicitly.

## Implementation

`corpus/descriptor.py` verifies the corpus, source terms, frame set and frame bytes, then writes a
restricted or public descriptor atomically under the corpus data root. The restricted tables carry
source and bundle records and a per-frame index. `corpus/descriptor_metadata.py` builds Croissant
1.1 metadata over those CSV tables; each row contains JSON. The output also holds a card, the versions
used and a copy of the frozen contract set. A repeat compares every output byte; a different output at
the same destination is refused. The generated slice is identified and excluded from encounter counts.
`declaration/dataset` 1.0.0 states the operator-supplied discovery facts. The validator is pinned in
its own `croissant` extra and used by a separate CI job, not by the runtime exporter.

The existing corpus, source and frame-bundle contracts mark no individual values public; the frame-set
bundle list is restricted. The public view therefore contains no record values, and states only split
counts. No existing restriction was relaxed. The review of potentially useful new public annotations
and their filtered export belongs to `public-descriptor-fields` in the plan.

## Acceptance evidence

| Gate | Command or artifact | Result |
| --- | --- | --- |
| Descriptor and disclosure | `.venv/bin/python -m pytest tests/corpus/test_descriptor.py` | restricted, public, locked, generated, refusals, deterministic bytes and integrity cases pass |
| Independent Croissant validator | `uv sync --locked --extra dev --extra croissant --python 3.12` then descriptor tests | 1.1.1 validates and loads streams, bundles and frames; public empty sets load |
| Declaration | `tests/schema/test_dataset_declaration.py` and `tests/schema/test_baseline.py` | valid example and missing discovery fields checked |
| Dependency boundary | `pyproject.toml` and `uv.lock` | `mlcroissant` is an optional extra, not a runtime requirement |
| Repository gate | `make ci` | pass: 1538 tests and all CI checks |

The first attempt could not resolve the validator because DNS was unavailable. Package access was
subsequently restored, and the pinned extra was installed before validation.

## Audit handoff

Reviewed sealed reads, source and frame-set pins, public disclosure, locked counts, output replacement,
contract copies and generated-case labels. Source seals and bundle hashes are checked again during
collection; tests exercise those checks. Public record tables are empty until the
[public fields task](../plan.md#public-descriptor-fields-optional) reviews and freezes justified
annotations. This limitation is routed there; no restriction is relaxed. The immutable destination
refuses a changed declaration, so `descriptor-refresh` owns a safe regeneration path.

## Close or resume

All acceptance gates passed. The descriptor work is removed from the forward-only plan and the
public-field refinement remains there. The plan holds 108 agent and 22 human
tasks; the next agent task is `decode-policy-reimport (optional)`, and the next human task is
`select-development-workload`. The `data-contracts` capability remains planned with open work.
