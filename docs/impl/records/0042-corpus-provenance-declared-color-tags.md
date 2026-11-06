# Declared color tags

## Task and scope

- Id / capability: `declared-color-tags` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `ef806fa`; clean worktree.
- Plan counts at start: 135 open (112 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=106, HUMAN-GATED=13, RUN NEEDED=6. Next agent `declared-color-tags (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### declared-color-tags (optional)

A source with no color matrix tag converts as BT.601, which misreads BT.709 content.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator can declare a missing color tag, recorded as declared and used
  in conversion.
- Scope boundary: Absent tags only. A declared value never overrides a stored tag, and nothing is
  guessed from resolution.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add an optional `color` declaration, record its origin, and pass it to
  `PixelConverter`.
- Acceptance gates: A declared BT.709 source converts pure red within two levels of its true value.
  A declaration that disagrees with a stored tag is refused, and an undeclared source behaves as
  before.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`color.matrix` is optional on a recording declaration. The names are the matrices swscale can
apply: `bt709` (1), `bt601` (6), `bt2020` (9), `fcc` (4) and `smpte240m` (7).
`src/ss_track/corpus/decoding/declared_color.py` records `declared_color` with origin `declared`
only when the stored matrix is unspecified and the pixel format uses a matrix. A matching stored
tag is omitted. A disagreement, and a declaration on a format that uses no matrix, are
`COLOR_TAG_CONFLICT` and publish nothing. `PixelConverter` passes the matrix only for a frame
whose own tag is unspecified.

`bt601` stores FFmpeg code 6 and is applied as swscale `Colorspace.ITU601` (value 5). Passing
code 6 does not select those coefficients. Each stream keeps its own converter.

The stored `color` object is unchanged, so an unspecified matrix stays 2. `declared_color` is
absent when unused, so an undeclared manifest stays byte-identical, and it stays outside the
bundle identity hash. A generated case copies the parent record, so it inherits the field. Adding,
dropping or changing the declaration after import is `IMPORT_CONFLICT` on import, amendment and
redecode, the same rule as the other capture facts.

Schema majors are unchanged. `declaration/recording` 2.3.0, `record/source-manifest` 2.3.0,
`record/frame-bundle` 3.2.0 and `result/command` 1.10.0 are the new minors. No new dependency,
environment variable or command flag. Current page:
[Declared color matrix](../current/corpus.md#declared-color-matrix). Specification section 4.1
states the operator declaration.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Declared BT.709 converts pure red within two levels, both frames, stored tag stays 2 | `tests/corpus/sources/test_declared_color.py::test_a_declared_bt709_source_converts_pure_red` | pass; pixels within 2 of `(255, 0, 0)`; no BT.601 warning; bundle `declared_color` is `{matrix: 1, origin: declared}` |
| Undeclared source stays BT.601 and omits the field | `test_an_undeclared_source_still_converts_as_bt601` | pass; first pixel `(233, 0, 2)` |
| A disagreeing stored tag is refused and nothing is imported | `test_a_declaration_that_disagrees_with_a_stored_tag_is_refused` | pass; `COLOR_TAG_CONFLICT` details `{declared_matrix: 6, stored_matrix: 1}` |
| A matching declaration keeps the undeclared manifest bytes | `test_a_matching_declaration_keeps_the_undeclared_manifest` | pass; repeat is `unchanged` |
| A matrix on a format that uses none is refused | `test_a_matrix_on_a_format_that_uses_none_is_refused` | pass; details name `gray` |
| Redecode keeps the declaration; a later add or drop is `IMPORT_CONFLICT` | `test_redecode_keeps_a_declared_matrix`, `test_an_amendment_cannot_drop_a_color_declaration`, `test_a_later_declaration_change_is_import_conflict` | pass; `changed_facts` is `sequence.declared_color` and the sealed bytes stay |
| The import command reports one refusal | `test_the_import_command_refuses_a_disagreement_in_one_record` | pass; exit `EXIT_REFUSED`, status `refused` |
| A declared matrix does not override a stored tag, and frame size does not choose one | `tests/corpus/decoding/test_pixels.py::test_a_declared_matrix_does_not_override_a_stored_tag` and `test_frame_size_does_not_choose_a_color_matrix` | pass; `bt601` conversion uses `Colorspace.ITU601`, whose value is not code 6 |
| `make ci` | `make ci` | pass; 1782 tests |

## Audit handoff

`none identified`. Reviewed declaration reading, import, redecode, amendment, staging conversion,
the bundle record, generated-case inheritance and the four contract minors.

Dropped, each because it needs no work:

- Range, primaries, transfer and chroma location stay stored tags. The task is the matrix, and
  this change found no misread of those tags to route.
- BT.470 BG has no swscale coefficients of its own, so it is not a declarable name. A file that
  stores it keeps that tag, and a `bt601` declaration disagrees with it.
- A declaration added after import is `IMPORT_CONFLICT`, the same rule as the other capture
  facts. The test locks the add, the drop and the redecode.

## Close or resume

Gates passed. Current page, specification section 4.1, contracts page, records index, and the plan
are updated. Plan counts after: 134 open (111 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
CLEAR=105, HUMAN-GATED=13, RUN NEEDED=6. Next agent `decode-interruption-safety (optional)`;
next human `define-locked-test-policy (optional)`. `corpus-provenance` stays `planned`.
