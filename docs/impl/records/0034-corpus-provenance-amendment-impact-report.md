# Amendment impact report

## Task and scope

- Id / capability: `amendment-impact-report` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `8f0a97e`; clean worktree.
- Plan counts at start: 130 tasks (108 agent, 22 human). Next agent:
  `amendment-impact-report (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### amendment-impact-report (optional)

After `--amend-terms` an operator learns which corpus versions hold the affected frames only by running
`corpus verify` on each, and a version nobody verifies stays unnoticed with its frames on disk.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track import --amend-terms` lists every corpus version on its data root
  that pins the replaced record, with its frames directory, for an operator's decision.
- Scope boundary: A report on one data root that refuses nothing and removes nothing, and never fails
  an amendment that is already recorded. Other hosts stay out of reach.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/`.
- Execution path: Scan with `scan_corpus_manifests` in `src/ss_track/corpus/versions/unlinked.py`
  for streams pinning the replaced seal. A corpus projection holds no pin, so add
  `source_manifest_sha256` to each major's projection in `corpus/records/projections.py`. Name a
  manifest the scan cannot read rather than skipping it.
- Acceptance gates: A source pinned by two versions lists both, a version pinning another record is
  not listed, an unreadable manifest is named and the amendment still records, and a repeat reporting
  `unchanged` lists nothing. One state gives one listing in one order.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`ss-track import --amend-terms` and `ss-track import --redecode` add `impact` when the command
replaces a source record. The field lists every corpus version on that data root whose streams pin
the replaced seal, each with the frames directory where that version's bundles are stored, and it
names a manifest, a version directory, or a major it cannot compare. The field is absent when there
is nothing to report, including a repeat that reports `unchanged`. The listing refuses nothing,
deletes nothing, and is not part of the source record. The scan runs after the new record is
written, inside the source lock, so a corpus directory that cannot be listed does not undo a
replacement already recorded.

`report_amendment_impact` in `src/ss_track/corpus/versions/impact.py` walks
`scan_corpus_manifests`. Corpus majors 2 and 3 project `source_manifest_sha256` beside the
placement fields. Corpus major 1 keeps no projection, because it held no group or split, and a
version of that major is named `other_schema`. A version is listed once, however many of its
streams pin the seal. Both lists are ordered by directory name. The frames path is the version's
bundle directory whether or not staging has created it. A generated case stores no pin of its own;
its parent stream does, and the version's frames directory covers the case frames.

The shared walk now reads version directories with `iterdir`. A version directory that cannot be
read is named `unreadable` instead of disappearing from the listing, and a corpus directory that
cannot be listed is `{"scan": "unreadable"}` on both this report and `unlinked`. A name with a
leading dot is not a version, and a directory that holds no manifest is not one either. The command
result contract gained minor `1.7.0` for optional `impact` and optional `unlinked.scan`. No
manifest schema, refusal code, environment variable, `pyproject.toml`, or `uv.lock` change.
`--redecode` lists the same way because a redecode has the same effect on versions that pin the
replaced record. Current page: [withdrawing rights](../current/corpus.md#withdrawing-rights).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A source pinned by two versions lists both, in one order | `tests/corpus/sources/test_amend_impact.py::test_one_state_lists_pinning_versions_and_names_what_it_cannot_read` | pass; `alpha`, `beta` and `zeta` pin the replaced record, ordered by directory name |
| A version pinning another record is not listed | the same test | pass; `other`, built from the second source, is absent |
| An unreadable manifest is named and the amendment still records | the same test, and `test_an_unreadable_corpus_directory_does_not_fail_the_amendment` | pass; bad JSON and a mode-0 version directory are `unreadable`, and a mode-0 corpus directory is `scan` while the new source record remains |
| A repeat reporting `unchanged` lists nothing | the same test | pass; the second command has no `impact`, and the staged frame bytes are unchanged |
| One state gives one listing in one order | the same test, and `test_a_version_is_listed_once_however_many_streams_pin_the_record` | pass; two streams with the same pin produce one version entry |
| A major with no projection is named rather than skipped | the same test | pass; corpus schema 1 is `other_schema`, and corpus schema 2 is matched |
| A redecode that replaces a record lists the pinning versions | `test_a_redecode_lists_versions_that_pin_the_replaced_record` | pass, through `main`; an unchanged redecode omits `impact` |
| An unreadable version directory or corpus directory is named on a build | `tests/corpus/versions/test_unlinked_scan.py::test_an_unreadable_version_directory_is_named_and_the_build_succeeds`, `test_an_unreadable_corpus_directory_is_named_and_the_build_succeeds` | pass; the build succeeds when the corpus directory can still be written |
| The command exits 0 and the result matches the contract | the command tests above | pass; the suite validates the logged result against `result/command` 1.7.0 |
| Required gate | `make ci` | pass: 1695 tests, format, lint, typing, complexity, shell, links, plan and contracts |

## Audit handoff

- Corpus major 1 is named `other_schema` and is not matched on its sequences. Dropped, needing no
  work: that major held no group or split, so a projection would make lineage compare a format that
  has neither, and the version is named so the operator sees it. The current page states this.
- Versions on another data root are not listed. Dropped, needing no work: the task and the
  specification limit the scan to one data root.
- A repeat that reports `unchanged` lists nothing, while the frames of the first listing stay on
  disk. Dropped, needing no work: the acceptance gate requires an empty listing, and the first
  command result is the report. The current page says the frames stay until an operator removes
  them.
- The shared walk used to skip a version directory it could not read, and it raised when the corpus
  directory could not be listed. Fixed in this change: both are named, and the naming does not fail
  a replacement already recorded. A corpus directory that also cannot be written still fails at the
  write, which is the existing commit path. Dropped, because the scan no longer hides or aborts on
  the listing itself.
- The listing is not sealed. Dropped, needing no work: it describes one data root at command time
  and is not part of the source record, as the specification says.
- A generated case stores no `source_manifest_sha256`. Dropped, needing no work: the parent stream
  holds the pin, and the version is listed once with the frames directory that holds the case
  frames.

## Close or resume

All gates passed. The current corpus page states the listing, its order, what it names, that a
redecode lists the same way, and that it is not part of the source record, and links this record.
The plan task is removed. Plan counts after: 129 tasks (107 agent, 22 human); next agent is
`case-preview (optional)`, next human is `select-development-workload`. `corpus-provenance` stays
planned because its other tasks remain. No service, port or external resource was started.
