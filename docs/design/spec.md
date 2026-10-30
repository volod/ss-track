# Agent Python Project Specification

## Purpose

The project provides a small, production-shaped Python base that a team can copy and immediately
develop with human and coding-agent contributors. It makes product intent, forward work, current
behavior, and quality gates explicit enough that a fresh contributor can select and complete work
without reconstructing unwritten process.

The specification is living. A product need discovered during implementation expands this document
through [Extending This Specification](#extending-this-specification). It is not a fixed scope
fence, but behavior that has no specification, boundary, or evaluation is outside the product until
those are declared.

## Design principles

The trust chain is:

```text
domain problem -> bounded capability -> evaluation -> forward task
               -> code and tests -> current-state documentation
```

The product specification answers what and why. The plan answers what remains. Current-state pages
answer what exists. CI checks the joins so completion is a state transition, not a status note.

## Scope

The starter repository includes:

- a Python 3.12+ `src` layout with an importable package and CLI;
- locked `uv` dependency management and Make entrypoints;
- deterministic tests, formatting, linting, typing, coverage, complexity, shell, and docs checks;
- GitHub Actions using the same CI entrypoint as local development;
- shared instructions for Codex, Claude, Gemini, and Cursor;
- a living capability registry and forward-plan/current-state lifecycle.

The starter does not choose a business domain, application framework, persistence layer, deployment
platform, or release policy. Those are product decisions and must enter through a specified
capability when needed. The example identity command proves packaging and execution only; it is not
an application architecture recommendation.

## Architecture

```text
Make and GitHub Actions
        |
        +-> package and CLI under src/agent_py/
        +-> mirrored tests under tests/
        +-> quality checks under src/agent_py/quality/
        `-> design -> plan -> current documentation lifecycle
```

Production behavior belongs below `src/agent_py/`. CLI parsing stays at the boundary and domain
logic moves to focused modules. Runtime artifacts resolve from `DATA_DIR` and never enter source
packages.

## Reproducible environment

The environment is created from `pyproject.toml` and committed `uv.lock`. Local development and
GitHub Actions both call Make targets and use the same locked development extra. Tool caches follow
`DATA_DIR`; the shared environment helper chooses `UV_LINK_MODE=copy` only when uv's cache and the
checkout live on different filesystems.

Boundary: the skeleton controls Python dependencies and checks. It does not install system packages,
provision external services, or guarantee reproducibility for undeclared tools.

Evaluation: a fresh copy reaches `make bootstrap` and `make ci` without manual repair. A negative
result names the missing command, stale lock, unsupported interpreter, or failing gate rather than
silently changing the environment contract.

## Project identity

The package exposes typed distribution, import-package, and version metadata. The `agent-py info`
command provides a minimal installed-path smoke test and a stable seam for replacing the starter
identity with the real product's first interface.

Boundary: the command reports identity only. It does not define configuration, service health,
deployment readiness, or product-domain behavior.

Evaluation: package import and CLI tests verify the same identity, while the build target produces
both source and wheel distributions. A negative result retains the minimal identity seam and records
why the proposed product interface is not yet ready.

## Documentation and planning integrity

`AGENTS.md` is the canonical contributor policy; tool-specific files are adapters. The product
specification, forward plan, and current-state tree have distinct ownership. Repository checks
validate relative links and anchors, capability registration, task metadata, lane-appropriate
statuses, group ordering, and forward-only plan language.

Boundary: these checks establish structural agreement. They do not decide which capability is
valuable, whether an evaluation threshold is ambitious enough, or whether a human judgment is
correct.

Evaluation: synthetic tests reproduce broken links, unknown capabilities, missing task fields,
wrong task lanes, and invalid ordering; the shipped tree passes the same checks. A negative result
blocks the change and points to the documents that disagree.

## Capability Registry

Every product capability appears here exactly once. Status is `planned` when the capability is
specified and has open plan work, or `shipped` when current-state documentation describes its
available implementation. A shipped capability may still have optional extension work.

Row order is the implementation line. Hard dependencies come first, then work that changes another
capability's evaluation inputs, then required work before capabilities with only optional work, then
upstream before downstream.

| # | Capability | Status | How it is evaluated | Implementation |
| --- | --- | --- | --- | --- |
| 1 | `reproducible-environment` | shipped | A fresh locked environment reaches the complete CI gate without manual repair | [Developer tooling](../impl/current/developer-tooling.md) |
| 2 | `project-identity` | shipped | Import, CLI, and distribution-build tests agree on the starter identity | [Product core](../impl/current/product-core.md) |
| 3 | `documentation-integrity` | shipped | Link, registry-plan, task-lane, metadata, ordering, and forward-language checks pass over fixtures and the repository tree | [Governance](../impl/current/governance.md) |

## Extending This Specification

A capability gap is a product discovery, not an automatic refusal and not permission for silent
scope growth. Use this lifecycle in order:

1. State the problem in operator or domain terms.
2. Amend the owning section of this specification, including what the capability does not do.
3. Declare the measurement, acceptance signal, and valid negative result before implementation.
4. Add a `planned` registry row with that evaluation.
5. Put tasks under the capability in the implementation line; every task declares `Serves`.
6. Build and evaluate, document available behavior under current state, remove finished plan scope,
   and change the registry row to `shipped` with its implementation link.

When implementation reveals that an existing capability has the wrong boundary, update its section
instead of creating an implementation workaround that the specification cannot explain.

## Specification and plan integrity

The registry and [implementation plan](../impl/plan.md) are two views of one product. The executable
contract requires:

- every task serves a registered capability and sits in its capability group;
- every capability declares an evaluation;
- every planned capability has at least one open task;
- every shipped capability links to current-state documentation;
- groups follow registry order in each task lane;
- every task declares the required outcome, boundary, execution, and acceptance fields;
- lane statuses match whether an agent can finish independently or a human action gates acceptance;
- required tasks precede optional refinements within a capability.

The check is structural by design. Product priority changes are made by editing the registry order,
not by adding heuristics to the checker.

## Success criteria

The skeleton succeeds when a team can copy it, rename it, create a locked environment, run a tested
package, and use any supported agent without duplicating project policy. A maintainer can determine
what the product promises, what work remains, which task is next in each lane, what behavior exists,
and how every capability is evaluated from repository files alone.
