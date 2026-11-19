# Runner

G0 and G1 events have one versioned meaning. The protobuf sources live in
`src/ss_track/contract/proto/`, the frozen descriptor sets live in `contracts/event/`, and
`ss_track.contract` checks a protobuf-JSON line. G2 fusion records are not in this set.
The [specification](../../design/spec.md#5-module-contract-execution-and-fault-semantics) states
the records. The [contract page](contracts.md) states how the registry holds the `event` family.

## Packages

Each file sets `ss_track.contract.v1.contract_urn` to
`urn:ss-track:contract:event:<id>:<version>`. The protobuf package is
`ss_track.event.<id>.v<major>`. Every field sets `json_name` to its proto name, so a line uses the
same snake_case names as the rest of the product. `int64` is a JSON string. A proto3 optional
field keeps presence, so `pts` of 0 is distinct from an absent `pts`. A non-optional `uint32` of 0
may be omitted and reads back as 0.

| Contract | Messages |
| --- | --- |
| `event/clock` 1.0.0 | `ClockTime`, `ClockDomain`, `EventRef` |
| `event/frame` 1.0.0 | `FrameRef` |
| `event/wire` 1.0.0 | `Box`, `Point`, `TargetSelection`, `Detection`, `TrackState`, `FrameResult`, `AdvisoryAction`, `RunEvent` |
| `event/analytics` 1.0.0 | `RunManifest`, `ValidationResult`, `SensorSample`, `ResourceSample`, `PowerSample`, `DerivedEnergy` |
| `event/trial` 1.0.0 | `InstrumentRecord`, `CalibrationRecord`, `HardwareTrial` |

Proto3 enum names share a package. Sample validity is `SAMPLE_VALID`, `SAMPLE_MISSING`,
`SAMPLE_STALE`, `SAMPLE_INVALID` or `SAMPLE_MULTIPLEXED`. A track that abstains is
`TRACK_ABSTAIN`; an advisory that abstains is `ADVISORY_ABSTAIN`. Score status stays `VALID`,
`NOT_SCOREABLE`, `UNSUPPORTED`, `NOT_MEASURABLE`, `RUNNER_INVALID` and `MODULE_FAULT`.

## Checking a line

```python
from ss_track.contract.events import parse_json_lines
from ss_track.contract.frame_ref import frame_ref_from_line, frame_ref_line
```

`parse_json_lines` skips blank lines, refuses duplicate keys and non-finite numbers, rejects an
unknown field, and then applies the meanings protobuf cannot state. A bad line raises
`RECORD_INVALID` with the line number and the reason. An absent optional field is accepted.
`ss-track contracts validate` does not parse these lines: naming an event contract is
`CONTRACT_UNKNOWN`, because the file is not one JSON document.

`frame_ref_line` and `frame_ref_from_line` round-trip the staged bundle `FrameRef`.
`content_frame_index` is the parent frame whose pixels are shown. `transform` is `identity` for a
source bundle and the generated-case transform otherwise. Display rotation is not this field.
The [frame reader](corpus.md#reading-frames) uses the same dataclass.

Other meanings the type system does not state:

- A framed event names one stream, bundle hash and frame index, and carries no interval. An
  unframed event names both interval ends and no frame. `FrameResult`, `TargetSelection` and
  `AdvisoryAction` acknowledge one frame. Empty detections are a valid `FrameResult`.
- A box has a positive half-open extent. A point's uncertainty is present and non-negative.
  `class_confidence` and `presence_confidence` are distinct and lie in `[0, 1]`. `MEASURED` and
  `PREDICTED` tracks carry a box. `CENTER` and `HOLD` name an instance.
- `MEDIA_PTS` with source `capture` is rejected. Clock uncertainty is present and non-negative.
- Watts use `W` and may be negative. Voltage and current use `V*A`. Joules are `DerivedEnergy`,
  unit `J`, over an unframed interval, with a method. A hardware trial stores trace hashes, not
  samples.

## Compatibility

`buf.yaml` selects the `WIRE_JSON` breaking category. A renamed field, a reused field number and a
changed `json_name` fail against a released image. An added field or a comment change does not.
`make proto-check` rebuilds each image and the Python bindings in a temporary directory, checks
registry pins and stage rules, compares committed artifacts, and runs lint and format checks. In the
released stage it also runs `buf breaking` against each frozen image. It is part of `make ci`.

In development, edit the proto and run `make proto-gen` to regenerate the `1.0.0` images, re-pin
registered event packages and refresh the bindings. The generator validates each updated contract
set as a batch before publishing it. It restores missing images together and refuses stale registry
or image snapshots; a failed publication rolls back written images and bindings. Readers may
temporarily refuse the set while image and pin writes are in progress; retry after generation
finishes. After a contract edit, regenerate affected development datasets as required
by the [development-stage rules](../../design/spec.md#177-development-stage-and-release). In the
released stage the generator refuses to overwrite a different frozen image; a new URN is required.
See the [development edit record](../records/0100-data-contracts-event-package-development-edit.md)
and [batch recovery record](../records/0101-data-contracts-event-package-batch-recovery.md).

A new released event version is classified without a JSON Schema diff. Identical descriptor bytes are
refused. A breaking change requires a major, migration text, and a disposition of at least `facts`,
because old JSON lines are not a view of the new message. A structure change that is not breaking is
a minor. Anything else, including a comment, is a patch. `ss-track contracts freeze` refuses
`event/`; the proto build publishes the image and the registry pins are reviewed with the rest of
the set. ODCS export and the reference dictionary skip event contracts.

An image embeds the files it imports. A change to `clock.proto` changes the bytes of `event/wire`,
`event/analytics` and `event/trial` as well. In development each affected image is re-pinned; after
release each affected package needs a new version. Dependency source locations are dropped from the
image. Comments on the event file itself remain and feed the meaning fingerprint.

## Modules and tests

| Module | Owns |
| --- | --- |
| `contract/proto/` | The sources and the buf lint and breaking configuration |
| `contract/build.py` | `make proto-gen` and `make proto-check` |
| `contract/development.py` | Stage and re-pin the complete development event set |
| `schema/compatibility/batch_publish.py` | Publish a validated batch with stale-input checks and rollback |
| `contract/breaking.py` | The buf commands |
| `contract/image.py`, `contract/image_shape.py` | Descriptor identity, structure and meaning fingerprints |
| `contract/events.py` | Parsing one named message from JSON Lines |
| `contract/frame_ref.py` | The staged `FrameRef` mapping |
| `contract/checks.py`, `contract/meaning.py`, `contract/meaning_records.py` | Meanings the type system does not state |
| `contract/gen/*_pb2.py` | Generated bindings. They stay out of format, lint, typing, complexity and the size report |

The runtime dependency is `protobuf`. The dev extra pins `buf-bin`, `grpcio-tools` and
`types-protobuf`. `tests/contract/` holds the golden lines, the `FrameRef` round trip and the
breaking mutations.
