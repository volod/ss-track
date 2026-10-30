# Agent Python Project Implementation Plan

Forward-only: this file describes work that remains. Available behavior and durable results belong
in [current-state documentation](current.md). Product behavior and evaluation belong in the
[specification](../design/spec.md).

Every task serves a capability from the
[capability registry](../design/spec.md#capability-registry). Capability groups follow registry
order in both lanes. Take the first required task in the earliest group that has one.

Task fields, statuses, ordering, and the capability-gap lifecycle are defined in the
[planning workflow](../guide/planning-workflow.md). Run `make plan-status` to view lane counts and
the next eligible work.

## Agent Implementation Tasks

### Project identity -- `project-identity`

#### personalize-template-project

Replace the starter identity immediately after creating a repository from this template.

- Serves: `project-identity` -- [Project identity](../design/spec.md#project-identity)
- Agent status: CLEAR
- Dependencies: Repository created from the template; target project name and description available
  from the owner or repository metadata.
- User-visible outcome: The Python package, installed command, and README identify and describe the
  created project instead of the template.
- Scope boundary: Rename `src/agent_py/` and every affected import, test, entry point, package setting,
  and tooling reference; update the README title, summary, setup examples, and repository layout.
  Do not choose a product framework, architecture, or deployment model.
- Data and artifact paths: `src/agent_py/`, `tests/`, `pyproject.toml`, `README.md`, `docs/`, and any
  package-name references in repository configuration or scripts.
- Execution path: Derive a valid distribution name, Python import name, and command name from the
  project name; move the package; update imports, configuration, tests, and documentation; install
  the renamed package from the lockfile; run its identity command.
- Acceptance gates: No stale starter-name reference remains where it denotes the active project;
  package import, CLI, metadata tests, `make ci`, and `make build` pass; the README accurately states
  the supplied project name and description. A negative result identifies missing or ambiguous
  owner-provided identity without inventing it.
- Documentation target: [Product core](current/product-core.md)

## Human-Assisted Tasks

No open human-gated tasks. Add work here when acceptance requires human judgment, authorization,
private access, or spending authority.
