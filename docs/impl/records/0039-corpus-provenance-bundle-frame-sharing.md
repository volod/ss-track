# Bundle frame sharing

## Task and scope

- Id / capability: `bundle-frame-sharing` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `b1878c9`; clean worktree.
- Plan counts at start: 137 open (114 agent, 23 human). Next agent
  `bundle-frame-sharing (optional)`; next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### bundle-frame-sharing (optional)

A generated case stores a full raw copy of every frame, even frames identical to its parent.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Frames a case leaves untouched take no extra disk space.
- Scope boundary: Hard links within one corpus version, falling back to a copy across filesystems.
  Hashes, records and read paths are unchanged.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Link in `store_frame` when a frame hash equals its parent's, with a
  scratch-to-bundle fixture.
- Acceptance gates: Bundle hashes match unlinked staging. Disk use on a short-window case falls by
  the untouched share, as measured, and `corpus verify` still names a damaged frame.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`store_frame` lives in `src/ss_track/corpus/bundles/frame_store.py`. A case passes the parent frame
it just read and that frame's sealed hash. When the stored bytes have that hash, and the parent file
is still the same size, the scratch name is a hard link. `publish_bundle` renames the scratch
directory, which keeps the link. `EXDEV`, `EPERM`, `ENOTSUP`, `EOPNOTSUPP` and `EMLINK` store a
copy of the same bytes. Any other link error propagates. Stream staging passes no parent, so a
decoded frame is still its own file.

The sealed index is the hash of the bytes either way, so `bundle_sha256` does not change. A repeated
frame links to the parent frame it shows, not to the frame at its own index. Free space reserved for
a case is the frames it may change when the parent bundle and the frames root share a device, and
every stored frame when they do not. A case that only drops or repeats frames reserves none.

`tests/corpus/bundles/test_frame_set_refusals.py` damages a frame the case rewrote. Frame 0 of that
shake is unchanged and therefore linked, so overwriting it names both bundles.

No new dependency, refusal code, environment variable, manifest field, or command field. Removing a
bundle is now `chmod u+w` on the directory only, because `chmod -R` would change the mode of a
parent frame the case links. Section 4.3 states the link. Current page:
[Generated cases](../current/corpus.md#staging).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Bundle hashes match unlinked staging | `tests/corpus/cases/test_frame_sharing.py::test_a_short_window_shares_untouched_frames_and_matches_a_copy` | pass; a copy forced by `EXDEV` has the same `bundle_sha256`, frame hashes and bytes, and no shared inode |
| Disk use on a short-window case falls by the untouched share | the same test, on this host's tmpfs | pass; 24 frames of 9216 bytes, window `[6, 16)`. Each inode occupied 12288 bytes. The case added 122880 bytes (10 frames) and did not store 172032 bytes (14 frames) |
| `corpus verify` names a damaged frame | `test_verify_names_a_damaged_frame_the_case_copied` and `test_verify_names_every_bundle_that_shares_a_damaged_frame` | pass; a copied frame is named alone, and a damaged shared inode is named for the parent and the case |
| Scratch publish keeps the link | `tests/corpus/bundles/test_frame_store.py::test_a_shared_frame_keeps_its_inode_when_scratch_is_published` | pass; the published name shares the parent inode, mode `0444`, and scratch is gone |
| `make ci` | `make ci` | pass; 1742 tests |

## Audit handoff

Reviewed the link decision, the space reservation, scratch publish, verification of a copied frame
and of a shared inode, removal of one name, and the documented bundle-removal command.

`none identified`.

Dropped, each because it needs no work:

- A same-size replacement of a parent frame between `read_frame` and `os.link` would seal the
  checked hash over the new bytes. The frame is mode `0444` and the gap is two calls in one process.
- A filesystem that shares a device id and then refuses links can pass the space check and then
  fail the copy. The command reports `STORAGE_FAILED` and publishes no case, which the current page
  states. The disk can also fill after a check that reserved every byte.
- The stage record does not count linked frames. This task keeps records unchanged, and disk use is
  the acceptance signal.
- Separate-inode reflinks would avoid a shared mode and shared damage. The task requires hard links,
  and verification names every bundle that shares a damaged inode.

## Close or resume

Gates passed. Current page, specification section 4.3, records index, and the plan are updated.
Plan counts after: 136 open (113 agent, 23 human). Next agent `import-stream-selection (optional)`;
next human `define-locked-test-policy (optional)`. `corpus-provenance` stays `planned`.
