# Case preview

## Task and scope

- Id / capability: `case-preview` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `878c810`; clean worktree.
- Plan counts at start: 129 open (107 agent, 22 human). Next agent
  `case-preview (optional)`; next human `select-development-workload`.
- Accepted task:

```markdown
#### case-preview (optional)

A declared region is a claim that an operator can only check by eye, and no tool shows it.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track corpus preview` writes a sheet of a parent frame beside its
  generated cases, with each region outlined.
- Scope boundary: One frame of staged bundles, read-only, as a PNG. No labelling interface.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add the command with the pinned encoder and a hand-checked outline position.
- Acceptance gates: One input gives identical PNG bytes. The outline lies on the declared pixels,
  and a frame a case removed is marked, not skipped.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`ss-track corpus preview` writes one PNG of a parent frame beside each generated case of that
stream, in `case_id` order. The parent panel is the stored frame. When a case's `region_status`
window contains the frame, the half-open rectangle's perimeter on that case panel is replaced
with RGB (255, 0, 0). A frame the case does not hold stays in the sheet as a solid RGB
(255, 0, 255) panel.

`src/ss_track/corpus/cases/preview_png.py` encodes `stored-deflate-rgb24-v1`: stored deflate
blocks, so the bytes do not depend on a zlib compressor. CRC-32 and Adler-32 are the checksums.
`src/ss_track/corpus/cases/preview.py` reads bundles through `open_frame_bundle` and writes only
`--out`, by replacing a scratch file. A path inside the corpus directory is refused. A missing
output directory is `STORAGE_FAILED` and names that path, not a scratch file. Naming a case id is
`CASE_INVALID` and names the parent.

Section 4.3 now states the sheet. `result/command` 1.8.0 adds optional `preview`. No new
dependency, refusal code, environment variable, or manifest field. Current page:
[Case preview](../current/corpus.md#case-preview).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| One input gives identical PNG bytes | `tests/corpus/cases/test_preview_png.py::test_one_input_encodes_to_identical_bytes_and_the_outline_is_only_the_perimeter` and `tests/corpus/cases/test_preview.py::test_the_sheet_matches_twice_and_outlines_only_the_declared_pixels` | pass; two encodes and two command runs match, including a frame larger than one stored block |
| The outline lies on the declared pixels | the same tests | pass; a hand-listed perimeter of `{x: 3, y: 2, width: 5, height: 4}` is the outline color and nowhere else, and a staged region differs from its case frame only on that perimeter |
| A frame a case removed is marked, not skipped | `tests/corpus/cases/test_preview.py::test_a_removed_frame_is_marked_in_place` | pass; the third panel is RGB (255, 0, 255) and the sheet width is three frames |
| Read-only bundles and refusals leave `--out` | `tests/corpus/cases/test_preview_limits.py` | pass; a case id, a missing stream, a missing case, a path inside the corpus, and a missing directory write nothing |
| Command result matches the contract | the command tests above | pass; the suite validates the logged result against `result/command` 1.8.0 |
| `make ci` | `make ci` | pass |

## Audit handoff

Dropped, each because it needs no work:

- The PNG is not compressed. Stored blocks are what keep one input's bytes identical across zlib
  builds, and the current page states the size.
- A perimeter that was already RGB (255, 0, 0) is not a second color. The parent panel is the
  stored frame, and the result names the rectangle.
- The PNG does not print case names. Panels run parent, then `case_id` order, and the result lists
  them. A caption would need a font and would be a labelling surface this task excludes.

## Close or resume

Gates passed. Current page, records index, and the command contract are updated. The task is
removed from the plan. Plan counts after: 128 open (106 agent, 22 human). Next agent
`staging-single-pass (optional)`; next human `select-development-workload`. `corpus-provenance`
stays planned.
