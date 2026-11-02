# Data contract and telemetry design

## Task and scope

- Id / capability: `data-contract-and-telemetry-design` / `data-contracts`, `telemetry-ingest`
- State: accepted
- Source: owner request at `e02a81d`: define all interchangeable data as open schemas with evolution
  support, judge the fl-op approach, record the organizational folder in `.env`, and research board
  and sensor telemetry for schema-driven adapters. The worktree held the owner's uncommitted change to
  record 0011, which this work leaves untouched.
- Plan counts at start: 87 tasks (66 agent, 21 human). Next agent: `source-terms-amendment`; next
  human: `select-development-workload`.
- Accepted task: ad hoc, with no plan block.
- Amendments: none.

## Implementation

This change writes no production code. It adds specification sections 17 and 18, two capabilities and
21 tasks, and the design pages [data contracts](../../design/data-contracts.md) and
[telemetry sources](../../design/telemetry-sources.md).

Decisions:

- JSON Schema 2020-12 in a restricted dialect holds document structure, and Protobuf holds events.
  fl-op's process is adopted: registry, frozen baselines, two fingerprints and a CI gate. ODCS becomes
  an optional generated view, because it cannot state a tagged union or a closed object.
- A sealed record keeps stamping only a major, because a minor inside a seal would change every hash
  on every additive release. Every shipped `schema_version: N` becomes contract `N.0.0` with no byte
  changed.
- The fl-op physical, canonical and mapping layering fits telemetry, where many sources share one
  meaning, and does not fit corpus records.
- `telemetry-ingest` is entirely optional and gates nothing in M1 to M3. It is milestone M6.
- A descriptor needs one operator declaration, because Croissant requires a license and an address
  that no sealed record holds.

The working tree's new environment variable is `ORG_ARTIFACTS_DIR`, set in the untracked `.env` and
documented in `.env.example`. No code reads it.

`/spec` was invoked under the routing rule. Its flow files a GitHub issue after interrogation, and the
request named repository documents, so its quality standards were applied and nothing was filed.

## Acceptance evidence

One-off spikes on an i9-14900K. Scripts not kept.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Shipped documents can be stated in JSON Schema | Hand-written draft schemas against a real recording and corpus, and a real frame set from `ss-track import`, `corpus build` and `corpus stage` on a generated FFV1 clip, with `jsonschema` 4.26.0 | Pass. A tagged union refused another transform's parameters. Source and bundle manifests were inspected, not schema-checked: their contracts are `corpus-contract-baseline` work |
| Schema alone against today's reader | Probes of `1.0`, NaN, infinity, a reversed window, a date object, an impossible date, a blank string and a boolean | Four differences, each with a handling in the design |
| Cost of validating on every read | One million frame rows, `Draft202012Validator.is_valid` against `json.loads` | 15.2 s and 15.0 s against 0.34 s |
| Compatibility classification | `jsoncompat` 0.5.0 `check_compat`, both roles, on a closed object | All ten structural kinds matched the rule table. An annotation is invisible to it |
| Croissant from sealed records | Generated JSON-LD loaded with `mlcroissant` 1.1.1 | Zero errors, one recommendation (`citeAs`). Streams, bundles and the per-frame index loaded. A `FileSet` of `.rgb24` with `application/octet-stream` failed: `None of the provided encoding formats ... returned a valid pandas dataframe` |
| ODCS as a generated view | A frame-set projection validated by `jsonschema` against the official `odcs-json-schema-v3.2.0.json` | Zero errors on one nested contract. The projection lost nothing there because that contract has no tagged union |
| Contract files ship in a wheel | A throwaway project with a `package-dir` mapping of a root `contracts/`, built with `uv build` | Pass: JSON and YAML present under the mapped package |
| Schema-driven decode | Synthetic ULog, 208 MB, 4.28 million messages. NumPy dtype per format against `pyulog` 1.3.0, three runs | 4.87 to 5.02 against 1.98 to 1.99 million messages per second, with timestamps, one gyro axis and voltage equal. The file was synthetic with three topics, and the host is not a target |
| Parquet bytes depend on the library | `pyarrow` 26.0.0 `read_metadata(...).created_by` | `parquet-cpp-arrow version 26.0.0` |
| Dependency footprint | `uv pip list` in clean environments | `datacontract-cli` 49 packages, 74 MB. `mlcroissant` 29 packages, 233 MB |
| Plan and spec agree | `make quality`, which runs the CI checks, coverage, Markdown lint and a package build, and `make ci` | Pass: exit 0, 656 passed, 0 spec-plan findings, 0 broken links |

The first ULog comparison was invalid: `pyulog` flagged the file as corrupt and stored nothing, so its
time was not comparable. The spike had written trailing padding, which `pyulog` does not expect. The
figures above are from the corrected file, and that nuance is in the telemetry page.

## Audit handoff

Each item below is stated in the text of its owner.

- `AUD-data-contract-design-1`: `require_schema` accepts one exact version, against section 15.
  Owner: `contract-enforced-readers`, with the wider reading in `record-read-window`.
- `AUD-data-contract-design-2`: version constants are shared across formats. Owner:
  `corpus-contract-baseline`.
- `AUD-data-contract-design-3`: sealed color values are unexplained FFmpeg integers. Owner:
  `corpus-contract-baseline`.
- `AUD-data-contract-design-4`: raw frames are unreadable to a general dataset loader. Owner:
  `dataset-descriptor`, which indexes them and states the layout.
- `AUD-data-contract-design-5`: real telemetry was not available here, so every format fact rests on
  documentation. Owner: `collect-telemetry-samples`.
- `AUD-data-contract-design-6`: `tegrastats`, Rockchip, Hailo and Coral details partly rest on
  community sources, as the telemetry page marks. Owner: `board-telemetry-sources`, whose fixtures
  must be recorded on real hosts before a profile claims a board.

## Close or resume

Every gate above passed. Plan after this change: 108 tasks (86 agent, 22 human). `data-contracts` and
`telemetry-ingest` are `planned`. Nothing was committed.
