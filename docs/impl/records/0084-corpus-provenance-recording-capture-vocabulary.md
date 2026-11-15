# Task Record

## Task and scope

- Id / capability: `recording-capture-vocabulary` / `corpus-provenance`
- State: active.
- Source: plan task; start commit `9c55a20`; no unrelated dirty files.
- Plan counts at start: 135 agent, 28 human; next agent `recording-capture-vocabulary`, next human `define-locked-test-policy`.
- Accepted task:

```markdown
#### recording-capture-vocabulary

The specification gives camera control a closed vocabulary, but a recording stores it as free text,
and no recording says whether its camera stood on the ground or flew. Reports cannot stratify by
either, so ground footage could stand in for an airborne observer unnoticed.

- Serves: `corpus-provenance` -- [Evidence lanes](../design/spec.md#2-evidence-lanes-and-claims)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A recording declares camera control and observer platform from closed
  vocabularies, a corpus build counts its encounters by both, and any other value is refused.
- Scope boundary: `capture.camera_control_mode` as `operator_steered`, `fixed_camera`,
  `autonomous_camera` or `unknown`, and `capture.observer_platform` as `ground_fixed`,
  `ground_handheld`, `airborne` or `unknown`, in the recording declaration and the source record.
  An absent value reads as `unknown`. A record written before this change keeps its bytes, and its
  free text is shown as stated and never mapped by guesswork. Other capture facts stay descriptive.
- Data and artifact paths: `contracts/declaration/recording/`, `contracts/record/source-manifest/`,
  `src/ss_track/corpus/declarations/`, `src/ss_track/corpus/versions/`, `tests/corpus/`,
  `docs/impl/workloads/`.
- Execution path: Evolve both contracts under the spec section 17.3 rules, with the version bump
  the change requires and a read disposition for older records. Add counts by control mode and
  platform to the build result, and restate the checked-in workload declarations.
- Acceptance gates: A value outside either vocabulary is refused with its field named. An older
  record reads with no byte or hash moved and reports its control mode as stated text. A build
  result counts encounters by control mode and observer platform, with `unknown` shown. Frozen
  contracts and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: The user authorized decomposition before implementation. The original scope is
  now owned by `source-capture-inspection`, `recording-capture-vocabulary` and
  `capture-encounter-counts`, in that dependency order. This record remains active; no original
  acceptance gate is claimed as delivered.

## Revised task allocation

The user authorized this decomposition; all original acceptance scope remains scheduled.

```markdown
#### source-capture-inspection

Historical capture descriptions need to remain visible when a newer source contract refuses them
as evidence. No operator-facing command currently exposes their original values and disposition.

- Serves: `corpus-provenance` -- [Capture compatibility](../design/spec.md#capture-vocabulary-and-historical-source-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Source inspection shows the stated capture fields, original major and seal,
  and evidence disposition, including a historical numeric or null control description.
- Scope boundary: Read-only inspection by source identity and optional retained-record seal.
  Missing platform is reported as unknown separately from the original fields. No classification,
  evidence promotion, media decoding or source mutation.
- Data and artifact paths: `src/ss_track/commands/corpus.py`, `src/ss_track/corpus/sources/`,
  `tests/corpus/`, retained source records under `$DATA_DIR/import/<source-sha256>/`.
- Execution path: Add `ss-track corpus inspect-source --source-sha256 HASH` with optional
  `--manifest-sha256 HASH`, using `read_stated` and existing source path validation. Keep domain
  logic outside the handler and state the command-result interface in its contract.
- Acceptance gates: Real retained records and text/numeric/null fixtures report exact original
  values. Missing records, bad identifiers, tampered seals and wrong kinds refuse. Inspection
  works without source media, writes nothing and preserves bytes and seals. Frozen contracts and
  `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).

#### recording-capture-vocabulary

Recording declarations accept arbitrary control descriptions and lack observer platform. Closing
these vocabularies without an explicit successor path would strand retained source evidence.

- Serves: `corpus-provenance` -- [Capture compatibility](../design/spec.md#capture-vocabulary-and-historical-source-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: source-capture-inspection.
- User-visible outcome: New sources declare closed capture values; an operator can migrate an old
  source explicitly while retaining its exact original record and all source bytes.
- Scope boundary: Control values are `operator_steered`, `fixed_camera`, `autonomous_camera`,
  `unknown`; platform values are `ground_fixed`, `ground_handheld`, `airborne`, `unknown`.
  Omission in a new declaration means unknown. Historical values are never mapped by guesswork.
  Only explicit capture amendment may replace these two judgments; other capture facts stay put.
- Data and artifact paths: `contracts/declaration/recording/`, `contracts/record/source-manifest/`,
  `src/ss_track/corpus/declarations/`, `src/ss_track/corpus/sources/`, `tests/corpus/`,
  `docs/impl/workloads/`, existing imported-source and retained-record paths under `$DATA_DIR`.
- Execution path: Freeze major 3 contracts with the previous major's `facts` disposition and a
  tested migration remedy. Protect both judgment properties in the compatibility gate. Add
  `import --amend-capture` through the shared source replacement transaction, composing with
  `--amend-terms` and `--redecode` when needed. Update declaration producers and workload YAML;
  restate only supported facts, using unknown otherwise. Keep all historical fixtures unchanged.
- Acceptance gates: Invalid values name the field. Every historical source major has a tested
  inspection and migration/refusal path. A successful migration preserves source identity, media,
  other capture facts, terms and decoded facts unless their explicit operation is also requested.
  Old records retain bytes and seals; repeated amendments are unchanged; interrupted publication
  loses no record. Pinned versions refuse and are listed; a successor builds with the same groups
  and splits. Metadata-only migration needs no media, and incomplete combined migrations publish
  nothing and name the missing operations. No new reproducible artifact kind is introduced.
  Frozen contracts and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).

#### capture-encounter-counts

A build reports split counts but cannot expose how much of its evidence uses each camera-control
mode or observer platform, leaving ground footage indistinguishable from airborne evidence.

- Serves: `corpus-provenance` -- [Capture compatibility](../design/spec.md#capture-vocabulary-and-historical-source-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: recording-capture-vocabulary.
- User-visible outcome: Build results report distinct encounter counts for every control-mode and
  observer-platform bin, including unknown and zero bins.
- Scope boundary: Count each encounter once in each applicable bin; mixed-stream encounters can
  enter several bins. Generated cases do not contribute. No score, joint histogram, inferred
  classification or claim that bin totals are additive.
- Data and artifact paths: `src/ss_track/corpus/versions/`, `tests/corpus/`, command-result contracts.
- Execution path: Reuse the verified source records used to build streams, retain capture data
  only as needed for the result, and avoid changing sealed corpus bytes for reporting alone.
  Document result field names and the multi-stream counting rule.
- Acceptance gates: Hand-counted fixtures cover every value, omission, repeated streams, mixed
  values in one encounter, multiple encounters and generated cases. A rerun has the same counts
  and manifest seal. Historical sources refuse with the migration remedy and count correctly
  after explicit amendment and successor build. Frozen contracts and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).
```

## Implementation

Investigation only. The 2.4.0 source contract permits text, numbers and null for
`camera_control_mode`. Restricting it to the requested vocabulary requires a major version.
The existing `facts` disposition preserves stated records but `read_sealed` refuses them as
evidence, while a `view` must not invent operator judgments. The legacy control value can also
be numeric, so preserving only text would lose a stated fact. Existing source replacement also
refuses changes to capture facts. A compatible read and reporting design needs to address all
three paths before the contract is frozen. No production or contract changes were retained.

## Acceptance evidence

No acceptance gate has passed; implementation remains to be done. Contract diff confirmed a major
bump is required for both declaration and source-manifest schemas. Baseline `make ci` passed
(2385 tests passed, 112 deselected), but it does not test the requested behavior.

## Audit handoff

Compatibility and a usable successor path belong to `recording-capture-vocabulary`; original
value inspection belongs to `source-capture-inspection`; reporting belongs to
`capture-encounter-counts`. Each task states its evidence and acceptance gates. The accidentally
duplicated record sequence was corrected before acceptance; no closed record was changed.

## Close or resume

State remains active. Design the older-record read path without guessing capture judgments or
changing sealed bytes, then implement the contracts, counts, regression tests and documentation.
The original task remains with narrower scope, alongside two required tasks. Capability status
is unchanged. The decomposition is recorded separately in record 0085.
