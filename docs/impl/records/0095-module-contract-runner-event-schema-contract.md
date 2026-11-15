# Event schema contract

## Task and scope

- Id / capability: `event-schema-contract` / `module-contract-runner`
- State: accepted
- Source: plan task at `479b5155bceebff20c4ffae3bbdd6cad3a474713`; the tree was clean.
- Plan counts at start: 158 open tasks (129 agent, 29 human). Next agent
  `generated-case-labels`. Next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### event-schema-contract

Python and later C++ modules need one versioned meaning for every event.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Modules and tools share a validated event schema with golden fixtures, and a
  breaking change fails CI.
- Scope boundary: The G0 and G1 record families. G2 fusion records are out of scope.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Define `.proto` files and protobuf-JSON JSON Lines validation. Add a Make target
  that regenerates bindings and a CI drift check, keep generated files out of the size and lint
  gates, and add the smallest justified dependency to `uv.lock`. Register each package under
  `contracts/event/`, pin `buf-bin` in the dev extra, and gate on `buf breaking` with the `WIRE_JSON`
  category against the frozen descriptor set, because G0 events travel as JSON. The registry,
  `make lint-contracts` and the contract `$id` pattern hold JSON Schema files only, so this task
  teaches them the `event` family.
- Acceptance gates: Golden fixtures cover absent and unknown fields, malformed payloads, coordinates,
  timestamps and power units. A malformed event is rejected with a reason. A renamed field, a reused
  field number and a changed `json_name` each fail the gate. `FrameRef` round-trips every
  field the staged bundle reports, including `transform` and `content_frame_index`, with those meanings.
- Documentation target: [Current implementation](current.md#areas), new page `current/runner.md`.
```

- Amendments: none.

## Implementation

Five event packages at 1.0.0: `clock`, `frame`, `wire`, `analytics` and `trial`. Each frozen file
is a descriptor set, `contracts/event/<id>/1.0.0.binpb`. The registry, the contract gate, ODCS
export and the reference dictionary treat that family as descriptors rather than JSON Schema.
`ss-track contracts freeze` and `ss-track contracts validate` refuse it. A line is checked by
`ss_track.contract.events`, and a staged `FrameRef` maps through `ss_track.contract.frame_ref`.

`make proto-gen` rebuilds images and Python bindings. It does not overwrite an image whose bytes
differ. `make proto-check` diffs a temporary rebuild and runs buf lint, format and `buf breaking`
with category `WIRE_JSON`. Generated `*_pb2.py` files stay out of the format, lint, typing,
complexity and size gates. Runtime dependency `protobuf==7.36.2`. Dev extra pins `buf-bin==1.75.0`,
`grpcio-tools==1.85.1` and `types-protobuf`.

A wire-incompatible later version is a major whose disposition is at least `facts`. An image embeds
its imports, so a `clock` change also changes the bytes of `wire`, `analytics` and `trial`. Those
frozen files stay immutable; the same change publishes a new version of each affected package.
Dependency source locations are dropped from the image so the well-known descriptor file does not
dominate the frozen bytes. Event-file comments remain and feed the meaning fingerprint.

Current page: [Runner](../current/runner.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Absent and unknown fields, malformed JSON, box extent, time base, power unit, and a reason on a bad line | `pytest tests/contract/test_events.py` | pass |
| Renamed field, reused field number, changed `json_name` fail; an added field and a comment do not | `pytest tests/contract/test_breaking.py` | pass |
| `FrameRef` round-trips every staged field, including `transform` and `content_frame_index` | `pytest tests/contract/test_frame_ref.py` | pass |
| Registry, freeze and validate know the event family | `pytest tests/schema/registry/test_event_family.py` | pass |
| Descriptor drift is inside CI | `make proto-check`, and `proto-check` is in the `ci-checks` recipe | pass |
| Full gate | `make ci` | pass: 2609 passed, 120 deselected |

## Audit handoff

- AUD-event-schema-contract-1, nonblocking: the sealed run manifest must store the `RunManifest`
  message of `event/analytics` and must not invent a second field list. Owner: `run-bundle-store`,
  amended in this change.
- AUD-event-schema-contract-2, nonblocking: G2 observations are a new event package. They must not
  edit the frozen G0 descriptor bytes or `FrameResult`. Owner: `sensor-observation-contract`,
  amended in this change.
- Dropped, no work needed: a JSON Lines subcommand. The checker is the library, and a command would
  change `result/command` without an acceptance gate in this task.
- Dropped, no work needed: C++ bindings. The task's gate is the Python binding drift check. The
  test plan states that C++ round trips are not claimed.
- Dropped, enforced here: an imported file's change cannot rewrite a frozen image. The history gate
  refuses the edit, and the runner page says the affected packages take a new version.

## Close or resume

Every gate passed. Current page [Runner](../current/runner.md), records index and plan updated.
After the plan edit, 157 open tasks remain (128 agent, 29 human). The next agent task is
`generated-case-labels`. The next human task is `define-locked-test-policy (optional)`.
`module-contract-runner` stays `planned`.
