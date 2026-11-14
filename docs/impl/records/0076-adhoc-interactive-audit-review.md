# Interactive audit review

## Task and scope

- Id / capability: `interactive-audit-review` / `self-supervised-corpus`
- State: accepted
- Source: user request; start commit `343ab81`; clean tracked worktree.
- Plan counts at start: 102 agent and 22 human; next agent `corpus-selection-evaluation`, next
  human `define-locked-test-policy (optional)`.
- Accepted request: "please assist me with review-video-corpus-sample in @plan.md If it can be
  possible, create interactive command to asists with review"
- Amendments: none.

## Implementation

Added `ss-track discover review-audit`, the terminal companion of `discover blind` for the human
task `review-video-corpus-sample`. The specification's blinded-audit paragraph in section 4.1a
states it and what it does not do. `corpus/review/audit_session.py` reads only the packet
(`review.yaml` for the audit id and item order, `items/` for pictures), resumes a saved review by
the same reviewer through the existing `read_audit_review`, and atomically writes a complete
`declaration/audit-review` 1.0.0 on every decision, with undecided items `unreviewed`.
`corpus/review/audit_interactive.py` holds the loop: include with one key per observation, exclude
with an observation, a reason and a note that `other` requires, edit notes, clear, navigate, and
an effort clock that caps the time between two answers at five minutes; `reviewer_minutes` rounds
it up, and a resumed session starts from the saved minutes. A seconds sidecar was dropped: the
sealed-read guard keeps every JSON and YAML parse in `corpus/` on its gate or a named loader, and
the packet template is parsed with `core/strict_yaml.py` instead. `corpus/review/audit_viewer.py`
loops an item's pictures in `ffplay` and offers an amplified `tblend` difference view, so a small
moving bird stands out, plus the desktop folder opener for zooming.

The controlling-terminal handling of `discover review-links` moved to `core/terminal.py`, and both
commands use it. The result is the existing `recorded` status with `record_path`, so
`result/command` stays 1.26.0. No declaration contract, dependency or environment variable changed.

Rejected: a local web page, which would need a server, more code and a browser for the same
decisions; editing the packet's `review.yaml` in place, which would make a repeated `discover
blind` of the same packet `CORPUS_CONFLICT`; reading the private mapping to verify pictures,
which would put stream ids within the session's reach while `unblind` already checks them.

First use on the pilot packet found that `x` followed by a reason name (`quality`) at the
observation prompt dropped the exclusion with "Nothing changed". The exclusion prompts now take a
key or a name in either order and ask again after an invalid answer;
`test_an_exclusion_takes_names_either_order_and_asks_again` replays that input.

Limitations: the command cannot verify the blinding or independence a reviewer declares, and
nothing stops the reviewer from opening the queue templates. Both are stated under
[Limits](../current/corpus/review-and-freeze.md#limits) and need no work: a declaration is by
design not a verification. Current state:
[interactive audit review](../current/corpus/review-and-freeze.md#interactive-audit-review).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Decisions save, resume and stay a valid review | `tests/corpus/review/test_audit_interactive.py` | pass |
| A presented packet reviewed interactively unblinds | `test_a_session_on_a_presented_packet_unblinds` | pass |
| Link review unchanged after the terminal helper moved | `tests/corpus/links/test_interactive.py` | pass |
| Real packet reads | `read_packet` on `pilot-audit-grouped-20261113`: 104 items, 16 frames each; a no-decision session wrote a valid review to a scratch path, then removed | pass; no picture shown |
| ffplay image sequence and difference filter | `ffmpeg -framerate 4 -start_number 0 -i item-000/%03d.png` with and without the `tblend` filter to `-f null` | pass |
| Repository gate | `make ci` | pass: 2367 passed; the first run caught a JSON and YAML parse outside the sealed-read gate, fixed above |

## Audit handoff

None identified. Reviewed scope: the three new modules, the CLI wiring, the terminal helper
extraction and the documentation; the packet stays unmodified and no private record is read.

## Close or resume

Accepted. The human task `review-video-corpus-sample` stays in the plan, and its execution path
now names the command. Plan counts after: 102 agent and 22 human, unchanged.
