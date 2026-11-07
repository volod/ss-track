# Discovery records

A discovery run proposes candidate windows of staged frames for human review. Its records let a
reviewer reconstruct why each window entered the candidate list: the frames it names, where it came
from, which pinned model and preprocessing scored it, what selection decided with what
probability, and whether the independent audit sample holds it. These records describe
[video corpus formation](../../../design/spec.md#41a-self-supervised-video-corpus-formation).
[Discovery runs](discovery-runs.md) states the `ss-track discover` commands that write and verify
them through the functions below; [SSL selection](../../plan.md#corpus-ssl-selection) will add
scores and selection. The
[contract record](../../records/0051-self-supervised-corpus-corpus-discovery-contract.md) and the
[adapter record](../../records/0052-self-supervised-corpus-corpus-video-index-adapter.md) hold the
decisions and evidence.

A candidate is a proposal. A score is not a label, and nothing in these records authorizes a source,
verifies a species or places a window in a split.

## Records

One run is one directory under `$DATA_DIR/self-supervised-corpus/<run-id>/`:

| File | Contract | Holds |
| --- | --- | --- |
| `run.json` | `record/discovery-run` 1.1.0 | Frame set read, extractors, scores, hint sources and what became of their matches, pool, selection, audit design, the owner's source approval, one line per inventory and per feature record |
| `inventories/<stream-id>.json` | `record/candidate-inventory` 1.0.0 | Every candidate window of one stream |
| `features/<extractor-id>/<stream-id>.json` | `record/feature-rows` 1.0.0 | One extractor's row keys for one stream, and the seal of the vector file beside it |

The run seals each inventory and each feature record by hash, as a frame set seals its bundles. A
run is built in scratch and published by one rename under a lock, so a reader meets a whole run or
none. A run id never holds two different runs: repeating the same records changes nothing, and
different records are `CORPUS_CONFLICT`. Version 1.1.0 adds `source_approval`, `feature_rows` and a
hint source's `matches`, each optional, so a 1.0.0 record still validates. One inventory per stream
keeps each record bounded by its stream's length. As written, a golden pool candidate with two
scores takes about 650 bytes, so one hour of 25 frame per second video cut into eight-frame windows
is about 7 MB.

### Identity and rights

A run names its corpus version and the seal of its frame set. Each inventory names its stream,
encounter group, bundle hash, source hash and the seal of the source record whose terms it rests on,
and the bundle's half-open frame window. A run binds only to streams: a generated case is fixture
material, not discovered video. The writer and `verify_discovery` refuse a run whose frame set,
bundles, source records, groups or windows differ from what its corpus version staged on this data
root. The source-record seal names the terms the run read; current terms, such as an expired
`retain_until`, are checked when a corpus is frozen from reviewed candidates, not here.

### Windows

Every candidate names a half-open window of source frame indexes of its bundle, the same window
form a corpus manifest selection uses. A window never names a time alone. Its `origin` says how it
entered the inventory:

| Origin | Meaning | Audit |
| --- | --- | --- |
| `pool` | One window of the eligible pool. Pool windows tile the bundle at the run's `window_frames`, the last possibly shorter, with no gap or overlap | `sampled` or `not_sampled`, with its stratum's inclusion probability |
| `sibling_time` | An ss-video time mapped onto ss-track frames. It names a run hint source, which states the ss-video commit, ffmpeg version and sampling rate, and the slot index | Always `ineligible`: a sibling keyframe has no known inclusion probability |

Because the pool tiles every bundle, its size is the run's processed exposure, and a missing window
is a refusal instead of silent unprocessed video. The slot rule that turns a sibling slot into
frames is in [frame mapping](sibling-integration.md#frame-mapping); `verify_discovery` recomputes
each sibling window from the stream's pinned source record and refuses one that differs.

### Provenance

Each extractor states its architecture, package name, version and full commit, every library
version its rows depend on, each weight file's name, immutable revision, SHA-256 and size, device,
dtype and autocast, batch size, whether it read staged frames or sibling JPEGs, preprocessing
(resize, crop, interpolation, input size, mean and deviation) and its output dimension and
normalization. The [sibling study](sibling-integration.md#reproducibility) found rows depend on
batch size, device and weight file, and that sibling JPEG rows differ from staged-frame rows, so
each is a required field. A device pattern names one device, so a run that moved to the CPU mid-way
cannot state one. Each score names its method, revision, the extractors it reads and which end ranks
first; a candidate carries every score of the run, either `computed` with a value or `unavailable`
with a reason.

### Selection and audit

| Selection status | Fields | Rule |
| --- | --- | --- |
| `selected` | `rank`, `probability` in (0, 1] | Ranks across the run are 1 to their count, at most `budget` |
| `not_selected` | `probability` in [0, 1) | |
| `excluded` | `reason` | Not ranked. Stays in the audit pool |

A ranked window has a computed value for every score selection reads; one without them is excluded
as `features_unavailable`. A null selection `seed` means deterministic selection, whose
probabilities are exactly 1 and 0.

The audit design is `stratified_fixed_size`: simple random sampling without replacement inside each
stratum, with its own seed. Each stratum states its pool size and sample size; every pool window of
a stratum carries inclusion probability `sample_size / eligible_count`, and exactly `sample_size`
of them are sampled. Audit eligibility depends only on origin, never on selection, so excluded and
unselected windows stay measurable for missed positives.

## Interfaces

| Function | Module | Does |
| --- | --- | --- |
| `seal_discovery(run_body, inventory_bodies)` | `corpus/discovery/records.py` | Seals each inventory, then the run with one line per inventory; refuses any contract or rule violation as `RECORD_INVALID` |
| `write_discovery(data_root, records)` | same | Binds the run to its staged corpus, writes the inventories, then the run |
| `read_discovery(data_root, run_id)` | `corpus/discovery/reader.py` | Reads the run, each inventory and each feature record through the sealed read path, checks contracts, seals, rules and vector file hashes |
| `verify_discovery(data_root, run_id)` | same | `read_discovery`, then the binding to the frame set and corpus manifest, the slot rule for each sibling window and the bundle frames for each feature row |

`seal_discovery` also takes the sealed feature records and adds one run line per record.
`run_rules.py`, `inventory_rules.py` and `features.py` check what the contracts state in words under
`x-rules`; `binding.py` and `sibling_check.py` check a run against its corpus. A rule refusal lists
every finding with its record (`run` or `inventories/<stream-id>`), JSON pointer, `x-rules` key and
message:

```json
{"record": "inventories/one", "pointer": "/candidates/2/selection/probability",
 "rule": "selection", "message": "deterministic selection gives not_selected probability 0.0"}
```

A missing or altered record is `RECORD_TAMPERED`, an inventory that is not the one its run sealed
is `RECORD_TAMPERED`, a resealed record that breaks its contract is `RECORD_INVALID`, and a run over
another frame set is `FRAME_SET_MISMATCH`.

A consumer with only `contracts/` and a standard JSON Schema validator checks each record's shape,
including a sibling window without frames, a missing rights reference and an impossible
probability. The cross-record rules need ss-track or a reader that follows the `x-rules` text.

## Limits

- Crop modes are `center` and `none`. Tiled coverage adds a mode with its grid as a contract minor,
  owned by [SSL selection](../../plan.md#corpus-ssl-selection).
- Pool windows do not overlap, and the only audit design is `stratified_fixed_size`; another
  stride or design is a contract minor when a consumer needs it.
- `source_approval` names an approval kept outside ss-track; the run cannot check that it exists.

## Verification

```bash
.venv/bin/pytest tests/corpus/discovery tests/schema/registry/test_standalone.py
.venv/bin/ss-track contracts validate --file tests/schema/examples/record-feature-rows.json
.venv/bin/ss-track contracts validate --file tests/schema/examples/record-candidate-inventory.json
make ci
```

`tests/corpus/discovery/` builds a golden run over two streams from stated facts and over a really
staged corpus. `test_discovery_contract.py` holds the golden records byte for byte against
`tests/schema/examples/` and the contract refusals, `test_discovery_rules.py` the rule findings, and
`test_discovery_store.py` writing, reading, tampering and binding. `test_standalone.py` validates
the examples and refuses ambiguous candidates with only `contracts/` and `jsonschema`.
