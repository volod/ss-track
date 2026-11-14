# Source capture inspection

## Task and scope

- Id / capability: `source-capture-inspection` / `corpus-provenance`
- State: accepted
- Source: plan task; start commit `6b20d0c`, clean worktree.
- Plan counts at start: 165 (137 agent, 28 human); next agent `source-capture-inspection`, next human `define-locked-test-policy`.
- Accepted task:

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
```

- Amendments: none.

## Implementation

`corpus/sources/inspection.py` uses `read_stated` to expose the original capture object, major,
seal and disposition. It validates both SHA-256 path components and checks the requested seal,
without opening source media or writing artifacts. The CLI routes through the existing report
handler. Missing platform is reported separately as unknown. The architecture guard explicitly
allows this inspection reader, which does not serve evidence. Frozen `result/command` 1.27.0 adds
the result interface. No dependencies or data kinds changed. See [Corpus](../current/corpus.md).

## Acceptance evidence

- Historical majors 1 and 2, text/numeric/null controls, retained selection, unchanged bytes,
  missing media and refusal cases: `tests/corpus/records/test_source_inspection.py`.
- An inspection of the configured data root read 38 current source records, compared their stated
  capture and seals, and confirmed unchanged bytes. No replaced records were present there.
- Architecture read boundary: `tests/corpus/records/test_sealed_reads.py`.
- Frozen result contract is exercised by the suite-wide output validation fixture.
- `make lint-doc-links` and `make lint-spec-plan`: passed.
- `make ci`: passed, 2394 tests passed and 112 deselected; format, lint, typing, complexity,
  shell lint, documentation links, plan integrity and frozen contracts also passed.

## Audit handoff

No findings identified. Reviewed source path validation, retained-seal selection, read-window
behavior, output contract, byte preservation, and the architecture guard. Future closed capture
vocabulary and explicit migration remain owned by `recording-capture-vocabulary`.

## Close or resume

All gates passed. The current corpus and contracts pages describe the interface, and the plan
has 136 agent and 28 human tasks, with `recording-capture-vocabulary` next in the agent lane and
`define-locked-test-policy` next in the human lane. Capability status is unchanged.
