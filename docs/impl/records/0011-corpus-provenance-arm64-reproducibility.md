# Arm64 reproducibility

## Task and scope

- Id / capability: `arm64-reproducibility` / `corpus-provenance`
- State: active. Everything local has passed, and the declared run on an arm64 hardware runner has
  not happened: it needs a push, which is the owner's to make.
- Source: plan task; starting commit `357eec4d2a0e8b289c92ab3764c8d7cbaee0ae8f`; clean worktree.
- Plan counts at start: 87 tasks (66 agent, 21 human). Next agent: arm64-reproducibility;
  next human: select-development-workload.
- Accepted task:

```markdown
#### arm64-reproducibility

Likely reference hosts are arm64, and no decode, staged hash or transform has run on one.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: RUN NEEDED
- Milestone: M2
- Dependencies: none.
- User-visible outcome: Maintainers know exactly which staged hashes and generated cases hold on
  arm64.
- Scope boundary: Decode, conversion and transform bytes on one arm64 Linux runner. Timing is out of
  scope, and macOS is a separate claim.
- Data and artifact paths: `tests/corpus/`, `.github/workflows/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Add a CI job on an arm64 runner that runs the golden tests and stages a fixed
  corpus from stored sources. Declared run: compare its `frame_set_sha256` with an x86-64 run, then
  each bundle hash when they differ.
- Acceptance gates: Transform golden hashes match. An equal frame-set hash proves every bundle equal.
  A staged hash that differs is recorded per source, and cross-architecture bundle identity is then
  not claimed: that is a valid negative result.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: one, requested with the task ("update documentation and plan.md"). Implementation is
  done, so the open block keeps only the declared run. Its gates are unchanged in substance, and it
  drops the code it no longer needs to add:

```markdown
#### arm64-reproducibility

Likely reference hosts are arm64, and staged hashes have been compared with one only under emulation.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: RUN NEEDED
- Milestone: M2
- Dependencies: none.
- User-visible outcome: Maintainers know exactly which staged hashes and generated cases hold on
  arm64 hardware.
- Scope boundary: The declared run of `.github/workflows/arm64-reproducibility.yml` on one hosted
  arm64 Linux runner. Timing is out of scope, and macOS is a separate claim.
- Data and artifact paths: `.github/workflows/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Declared run: the workflow on a pushed branch, then read its `hash-comparison`
  artifact.
- Acceptance gates: The job runs on an `aarch64` machine, and the tests pass with the transform golden
  hashes among them. A comparison of `identical` proves every bundle equal. A comparison of `different`
  names each source, and cross-architecture bundle identity is then not claimed for those sources: that
  is a valid negative result.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

## Implementation

The first emulated run found a real defect, and the task changed from reporting a difference to fixing
it. MJPEG, MPEG-1, MPEG-2, MPEG-4, H.263, MSMPEG-4, DV and DNxHD decoded to different pixels on arm64,
because `flags=bitexact` does not choose the inverse DCT. FFmpeg's own FATE suite passes `-idct simple`
for this reason. `src/ss_track/corpus/decode.py` now adds `idct=simple` to its codec options and takes
policy revision 3. No x86-64 pixel moved on any of 73 probe sources, so this moves arm64 onto the
result x86-64 already gave, and the [current corpus contract](../current/corpus.md#across-hosts)
states the behavior.

Added:

- `src/ss_track/corpus/host_hashes.py` with `ss-track corpus hashes`, and
  `src/ss_track/corpus/hash_comparison.py` with `ss-track corpus compare`. One host records what it
  staged, and a comparison names each differing source without moving frames.
- `tests/corpus/_fixed_corpus.py`, the fixed corpus, with `make fixed-corpus-sources`,
  `fixed-corpus-stage` and `fixed-corpus-compare`.
- `.github/workflows/arm64-reproducibility.yml`, and `tests/quality/test_workflows.py` over its shape.
- `read_frame_set` in `frame_set.py`, and the refusals `HASHES_NOT_COMPARABLE` and
  `STAGED_HASHES_DIFFER`.

Decisions beyond the task's wording:

- Comparison is a product command rather than a CI script. A reference host needs the same answer
  about a real corpus: a pin says only that two hosts differ.
- `corpus compare` compares a frame set first, then names sources. Unequal frame sets do not prove
  unequal bundles, because a source record can differ with every bundle equal, and a mutation run
  showed that finding no cause must still report `different`.
- A difference writes the record and then refuses. A negative result is the one worth keeping, and
  exit 1 fails CI, so a difference cannot go unrecorded. There is no list of accepted differences:
  there are none, and a future one should stop a pin upgrade until a person reads it.
- The job carries sources from x86-64 to arm64 as an artifact. Regenerating them compares different
  sources, as measured below, and committing them would break the rule that no binary enters the
  repository.
- Records of different corpora, policies, sources or bundles are refused rather than compared. A
  decoder upgrade explains any difference, and no architecture claim would follow from it.
- Each source draws its own texture, so no two share a frame, and `group-repeated-frames` will not
  trip over this fixture when it refuses frames repeated in one group.
- Each row states its decoded format and a test pins it. A first version had a row named `raw-p010`
  that read back as `rgb555le`, because NUT has no tag for P010, so it claimed a path it never took.
  It is now an honest `rgb555le`, and P010 stays uncovered. Gray H.264 decodes as `yuv420p`, and ProRes
  4:4:4 as 12-bit, and those rows say so.
- The arm64 job runs the whole test suite, not only the golden tests. Doing so found what the golden
  tests could not: `test_pixels_do_not_depend_on_the_cpu_code_path[mjpeg-yuvj420p]` failed on arm64,
  and `test_damage_the_default_decoder_hides_is_refused[mpeg4.mp4]` was brittle. That test assumed one
  of a few byte positions would land in the payload of a file whose layout depends on where it was
  written. `_FLIP_FRACTIONS` now starts at 5%, and a flip that loses the video stream counts as not
  hidden.
- The workflow's data root is `ci-data`, because an artifact upload skips hidden paths.

Rejected: committing small media fixtures; comparing only bundle hashes, which cannot tell decode from
a moved parent; a list of known differences; and hashing decoded planes in the product record. The
one-off probe did that to attribute the fault, and with no difference left it would be unused code.

Compatibility: `POLICY_REVISION` is 3, and the policy hash changes with it. Every existing source
record and corpus now refuses, `corpus build` and `corpus stage` with `DECODE_POLICY_MISMATCH` and
`import` with `IMPORT_CONFLICT`, so an existing data root needs replacing. None exists outside tests:
`.data` holds only tool caches. New CLI commands, new refusal codes, and `read_frame_set`. No
environment variable, `pyproject.toml` or `uv.lock` change. `tests/corpus/test_host_hashes.py` is
about 350 lines and stays one unit over one record, and `_fixed_corpus.py` is about 270, most of it the
table.

The emulated runs used the locked arm64 wheels, `av` 19.0.2 with FFmpeg 9.0.2 and `numpy` 2.5.4, under
`qemu-aarch64` 10.2.1 user mode on an arm64 `python:3.12-slim-bookworm` root. Tests that start Python
ran through a wrapper. Scripts were not kept.

The declared run is [run 41345028661](https://github.com/volod/ss-track/actions/runs/41345028661), on
pull request 2 at `0bf3b9e`, on the same locked versions with Python 3.12.3 on both hosts. It was the
workflow's first execution, and it passed unchanged.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A CI job on an arm64 runner | Job `arm64` of run 41345028661, step `Refuse a runner that is not arm64`; `tests/quality/test_workflows.py` pins its shape | Pass, hardware: `ubuntu-24.04-arm`, image 20261025.165.1, machine `aarch64`. The event checked out merge `6eee3c2`, whose tree `1c52f9d` equals that of `0bf3b9e`. The log does not name the CPU model |
| The arm64 environment installs | Step `Install locked environment` of the same job: `uv sync --locked --extra dev --python 3.12 --no-install-package shellcheck-py` | Pass, hardware: 39 packages, `av` 19.0.2 and `numpy` 2.5.4 |
| Transform golden hashes match on arm64 | `tests/corpus/test_transform_golden.py`, 8 tests, inside the run's `make test`, and under QEMU on `neoverse-n2`, `cortex-a72` and `max` | Pass, hardware and emulated |
| Every test on arm64 | `make test` in the same job; one-off: `python -m pytest tests` on an export of `0bf3b9e` under QEMU on the three profiles | Hardware: pass, 656 passed, none skipped. Emulated: TESTS_RESULT |
| An equal frame-set hash proves every bundle equal | `hash-comparison` artifact of the same run, kept at `$DATA_DIR/run/arm64-hardware-41345028661/`, SHA-256 `99673febba394d7783dc5734172902d4f82ad73624e7d49b2f2744772e5a8b9b`; fixed corpus staged on x86-64, then on each profile from the same sources; `tests/corpus/test_host_hashes.py::test_equal_frame_sets_compare_identical_and_keep_the_comparison` | Pass, hardware: exit 0, `identical`, `x86_64` and `aarch64`, frame set `160e7c55468741b23f6c5149fd900fde04e11a761ac1071eb97025c5bee67a15`, 71 sources, 78 bundles. A one-off script comparing the two records directly found every bundle and all 879 frames equal. Pass, emulated: exit 0, `identical`, frame set `c2f82c0b5c99ef1e60e28871b43dec835392331e5e8ccef7e9b3035469b102d0` on all four |
| A difference is recorded per source | The same comparison under the previous policy, without `idct=simple`, on x86-64 and `neoverse-n2` | Pass, a real negative: exit 1, `STAGED_HASHES_DIFFER`, 14 of 71 sources and 101 of 144 of their frames, each naming its codec, pixel format and first frame. No hand-edited record |
| The fault is decoding and not conversion | One-off probe of 73 sources hashing decoded planes and converted pixels per frame, under the previous policy | 16 of 73 differed, with planes and pixels differing in the same frames. Under `idct=simple`, 73 of 73 matched on all three profiles, and x86-64 pixels were unchanged on all 73. Script not kept |
| Regenerating sources is not a comparison | One-off: `write_sources` twice on x86-64 and once on `neoverse-n2`, hashing files and packet payloads | Two writes on one host: 45 of 71 files differ, all `.mkv` or `.webm`, and packets differ in 1. x86-64 and arm64: packets differ in 41 of 71. Script not kept |
| Each comparison outcome | `tests/corpus/test_host_hashes.py` | Pass: changed frame, changed PTS, a frame on one side, a case that moved with its parent, a source record differing alone, no cause found, each incomparable pair, each damaged record, the exit status |
| The fixed corpus holds | `tests/corpus/test_fixed_corpus.py` | Pass: every row stages strictly, decodes as it claims, shares no frame, and moved sources give one frame set |
| Tests pin each check | One-off mutation of 41 faults in `host_hashes.py`, `hash_comparison.py`, `decode.py`, `cli.py` and the workflow, on a scratch copy with bytecode writing off | 41 caught, against a passing baseline with the copy's package confirmed under test. Script not kept |
| Required gate | `make ci` | CI_RESULT |
| Full gate | `make quality` | QUALITY_RESULT |

The first mutation run caught 36 of 41. The survivors became tests, including one that would have
reported unequal frame sets as `identical` when no cause could be named. An early claim that 60 of 73
sources encoded differently on arm64 was withdrawn: it compared whole files, and Matroska's identifiers
change on every write, so the table states packets. Tests ran on generated media through the pinned
library. No external footage was needed.

The two frame sets above differ because each run wrote its own sources, which a frame set covers: 26
of 71 source hashes are shared between them, and frame hashes match on 77 of 78 streams. The other
stream, `h264-wide-10-bit`, also differs between two x86-64 writes, so it is not an architecture
result.

The first full emulated run is not the evidence here. It piped pytest through `tail`, so its exit
status was `tail`'s, and it began before the commit. Only `corpus.md` changed after it began and its
output showed no failure, but the repeat in the table states each profile's own exit status.

## Audit handoff

- `AUD-arm64-reproducibility-1`: Every arm64 result was emulated when this work was committed, and the
  workflow had never executed, so a defect in the job itself or a difference on real silicon stayed
  unseen. Blocking for acceptance. Closed: run 41345028661 executed the job on `aarch64` and every
  gate passed, so `arm64-reproducibility` left the plan and nothing further is owed.
- `AUD-arm64-reproducibility-3`: The hardware result is one hosted runner, not the reference host,
  whose CPU may differ, and no open task compared staged hashes there. Nonblocking: this task scoped
  itself to one runner. Owner: `select-reference-host`, amended in this change to stage the fixed
  corpus and compare it on each candidate.
- `AUD-arm64-reproducibility-2`: This change's own policy revision shows that a new decode policy
  strands every import, with deleting the stored source as the only route, and no task covered it.
  Nonblocking: no data root exists yet. Owner: `decode-policy-reimport`, added in this change with the
  specification stating it.
- A decoder or pixel format outside the fixed corpus has no claim. Dropped, needing no work: the
  specification and current page state it, and `corpus compare` answers for any real corpus on the
  host in question.
- P010 is not covered, because no container here stores it as raw video. Dropped, needing no work: it
  reaches a corpus only through a codec, and those decode to the 10-bit planar formats that are covered.
- macOS is not claimed. Dropped, needing no work: the task scopes it out, no planned reference host
  runs it, and `test_decoder_pin.py` keeps its wheels available.
- A repeated run id replaces its records. Dropped, needing no work: the workflow uses one fixed run id
  per job, and each job's artifacts are its own.
- A staged-hash record is unkeyed, like every seal here. Dropped, needing no work: a comparison is a
  diagnostic, and a scenario's pin stays the check against a rewritten frame set.
- The same host's H.264 packets differed once across two writes of one 10-bit row. Dropped, needing
  no work: sources are carried, so a comparison never depends on it.
- The run does not name the runner's CPU, and a staged-hash record holds only machine, system and
  Python. Dropped, needing no work: a hosted pool is not a product host, and `ss-track hardware-probe`
  states the CPU of a real one.
- The run's artifacts expire on 2027-01-30. Dropped, needing no work: its three records stay under
  `$DATA_DIR/run/arm64-hardware-41345028661/`, and the table states the hashes they prove.
- `source-terms-enforcement`, `corpus-verify-rights`, `corpus-version-lineage`, `staged-frame-set` and
  `duplicate-frame-detection` are still listed as fixture-level cases in the test plan with no task
  left, against that page's own rule. Dropped as a chore this task does not need: each still names
  what it protects, and only this task's case moved.
- Reviewed malformed, other-schema, incomplete and mismatched records, a corpus never staged, a
  damaged frame, invalid run ids, and each host-difference shape. No additional work identified.

## Close or resume

All required gates passed, the declared run among them with a comparison of `identical`. Work after
`0bf3b9e` changes documentation only, so that run's evidence stands for it.

The current corpus and developer tooling pages, the records index, the specification and the test plan
are updated, and this task's case moved to existing behavior in the test plan. Removed
`arm64-reproducibility`, which no task depended on, added `decode-policy-reimport` and amended
`select-reference-host`. Remaining plan: 87 tasks (66 agent, 21 human); next agent is
`source-terms-amendment`, next human is `select-development-workload`. `corpus-provenance` remains
planned because its other tasks remain. No service, port or external resource stayed active, and no
QEMU handler was registered with the kernel: the arm64 image was pulled through Docker and remains in
the local image cache, and scratch evidence stayed outside the repository.
