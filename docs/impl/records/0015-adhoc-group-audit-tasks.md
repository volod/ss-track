# Group audit tasks

## Task and scope

- Id / capability: `group-audit-tasks` / `documentation-integrity`
- State: accepted
- Source: owner request at `8802c7e`, clean tree: add to every task group, after its optional
  tasks, an agent audit of the group's implementation, run at higher effort.
- Plan counts at start: 110 tasks (88 agent, 22 human). Next agent: `decode-policy-reimport`; next
  human: `select-development-workload`.
- Accepted task: ad hoc, with no plan block.
- Amendments: none.

## Implementation

Each of the 24 Agent-lane groups gains `<capability-id>-audit (optional)` as its last task. Every
Human-lane group also has an Agent-lane group, so each capability has one audit.

`docs/guide/planning-workflow.md` gains `## Group audits`, which holds the protocol once: seven review
questions, the rule that a refactor moves no sealed byte, hash, score or refusal code, and how findings
route. Each task then holds only what is specific to its group: the risk, where to start and its gates.

`plan_integrity.py` gains `_audit_findings`: an Agent-lane group must end with its audit, marked
optional, with `Effort: high`. This is a new refusal and removes none. `_tasks_by_group` now serves
both it and the ordering check. `tests/quality/_plan_fixture.py` closes each generated group with an
audit, and a test can pass `audit=False`.

`AGENTS.md`, the planning workflow, the specification's planning integrity text and the governance
page state the rule. Both policy texts said an audit never becomes a task, which this request
reverses for one kind, so they now separate the per-change audit from the scheduled group audit.
`plan-dependency-integrity` is amended to read the audit's dependency sentence.

Decisions:

- **`(optional)` on a task that is not skippable.** The owner placed it after the optional tasks. A
  required task there fails the ordering rule, and exempting it would loosen the checker. It would also
  run first: `_next_task` sorts required work ahead of optional work within a group, so a required
  `corpus-provenance-audit` would be reported as next, ahead of all 14 optional tasks of its group. And
  `plan-dependency-integrity` will refuse required work that depends on optional work. A shipped
  capability may also keep only optional extensions, so a required audit could not sit under
  `documentation-integrity`. The marker therefore sets order, and the texts say that it does not mean
  skippable. An open audit keeps its capability `planned`.
- **One dependency sentence, not a list of ids.** A list would need an edit at every task removal, and
  a task added to the group could be left off it. The checker keeps the audit last, so position and the
  sentence say the same thing.
- **A checker rule beyond the request.** Without it the next task appended to a group lands after
  the audit, and a new group has none. "Every group" would stop being true without anyone noticing.
- **Ideas go to section 12.** A new task in the audit's own group keeps the audit open for that work
  alone. A feature with no evaluation yet goes to section 12, so an audit can close instead of feeding
  itself.
- **`Effort: high`** is a plain field, in the way `Milestone` and `Research` are. It records intent,
  and the operator or harness that starts the task applies it.

Rejected: a new `(audit)` heading marker, which changes the parser and every reader for a distinction
that the id already carries.

Compatibility: no CLI, record or dependency change. `make lint-spec-plan` refuses a plan that lacks an
audit. Adding a capability group now needs an audit in the same change.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Every group ends with its audit | `make lint-spec-plan` on the repository plan | pass: 0 findings. Before the tasks were added the same check failed the repository plan, shown by `test_repository_specification_and_plan_agree` |
| The rule refuses each breach | `test_a_group_must_end_with_its_audit`, `test_a_task_after_the_audit_is_rejected`, `test_a_required_audit_is_rejected`, `test_an_audit_must_declare_high_effort`, `test_the_human_lane_needs_no_audit` | pass |
| Audits do not jump the queue | `make plan-status` | pass: next agent stays `decode-policy-reimport` |
| A required audit would | One-off, not kept: `_next_task` on the repository plan with `corpus-provenance-audit` set required | Confirmed: reported `corpus-provenance-audit` instead of `decode-policy-reimport` |
| Named repetition is real | `grep` of `tests/corpus/` and `src/ss_track/corpus/` | Confirmed: `flock` in `staging.py` and `amendment.py`, `.incoming-` in `importer.py`, `PermissionError` handlers in both, `_rights` in three test modules, `cli_root` in two, a last-record helper in four. Other groups' start points come from their task text, as their code does not exist yet |
| Whole gate | `make quality` | pass: exit 0, 695 passed, 0 spec-plan findings, 0 broken links, package built |

## Audit handoff

- `AUD-group-audit-tasks-1`: the audit's dependency sentence is prose, and the checker keeps only its
  position. Owner: `plan-dependency-integrity`, amended in this change.
- `AUD-group-audit-tasks-2`: `make plan-status` may report an audit as next while another group's
  dependency is unmet, because it does not read readiness. Owner: `plan-dependency-integrity`,
  whose text states it.
- Dropped: an optional task nobody ever builds would hold its audit open. Dropping or finishing such
  a task is the owner's existing decision, and a rule here would only restate it.

## Close or resume

Every gate passed, as the table states. Plan after this change: 134 tasks (112 agent, 22 human). Next
agent: `decode-policy-reimport`; next human: `select-development-workload`. No capability changed
status. Nothing was committed.
