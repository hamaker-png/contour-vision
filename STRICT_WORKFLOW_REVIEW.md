# Strict workflow review — local handoff accepted

This redesign follows the user's separate request for a stricter critic, external-browser
trials and substantially more iterations. It does not reuse the earlier four-round result
as evidence that the new workflow is finished. The hard stop and full scope are recorded
in `WORKFLOW_REDESIGN.md`.

Completed twelve substantive review/fix/test cycles and final browser regression on
2026-09-19 at 18:30 New York time, before the 20:30 deadline. The independent critic
recommends local handoff with no unresolved critical journey gates.

## Review evidence

| Round | Workflow | Clarity | Editing | AI/family | Main finding resolved in following work |
|---|---:|---:|---:|---:|---|
| 01 | 3.5 | 5.8 | 4.0 | 2.5 | Demo contamination and no clear post-upload next action |
| 02 | 6.4 | 7.0 | 4.0 | 5.5 | Competing AI actions, fragile rearrangement and misleading transform-only export |
| 03 | 6.9 | 7.1 | 6.7 | 5.7 | Moving drag targets and lost conversation state |
| 04 | 7.3 | 7.2 | 7.0 | 6.8 | Validation provenance, adversarial intake and stale-state coverage still needed |
| 05 | 7.5 | 7.2 | 7.0 | 7.1 | Redo disappeared after undo returned to the Images screen |
| 06 | 7.7 | 7.5 | 7.6 | 7.1 | Compact prefixes, global history and long/nested editing verified |
| 07 | 7.8 | 7.5 | 7.7 | 7.2 | Phone handoff and in-flight parameter/name preservation verified |
| 08 | 8.0 | 7.7 | 7.7 | 7.4 | Incremental execution, cancellation, exact retry and failed-score exclusion verified |
| 09 | 8.1 | 7.8 | 7.7 | 7.6 | Per-image review and individual labels added; pending-coordinate loss and missing detection IDs found |
| 10 | 8.4 | 8.1 | 8.0 | 7.7 | Both P1 gates closed; numbered/error-localized results, pending-edit integrity and three exact browser exports verified |
| 11 | 8.6 | 8.3 | 8.2 | 8.3 | Zoomed precision, explicit units, consolidated labeling and example/validation boundaries verified; touch panning found |
| 12 | 8.8 | 8.4 | 8.4 | 8.3 | Touch Pan/Draw and multi-touch cancellation verified; reproduced close/reopen race fixed and all 18 retest trials passed |

Round 12 passes all twelve direct gesture, drawing and save checks. It also preserves a
reproduced close/reopen loading failure and eighteen successful post-fix trials. Numeric
scores support prioritization; the eight acceptance criteria determine completion.

The independent reports in `artifacts/strict/strict-round-01.md` through
`strict-round-12.md` contain actual standalone Chrome actions, findings and their closure. Browser
reviews explicitly foreground the selected Chrome tab. An early background-tab focus
finding was withdrawn after a controlled foreground reproduction passed; that correction
is preserved in round 03 rather than presented as a product fix.

## Final requirement audit

| Requirement | Accepted evidence | Scope and limits |
|---|---|---|
| Clean image-family intake | Rounds 05/07: mixed corrupt/valid atomicity, duplicates, 12/13-file boundary, cancelled obsolete upload, actual phone upload | Verified independently in round 11 |
| Immediate AI-guided handoff | Rounds 04/07: automatic family inspection, no-key setup, retained answers, questions and review/accept flow | Live model quality remains unverified without an API key |
| Linear, revisitable workflow | Four stages, image-only/analyzed save/open, cross-screen history, photo/2D label-review-export journeys | Final seven-scenario regression passed |
| Comfortable, reversible editing | Foreground drag/keyboard, type preflight, stable gaps, compact shared prefixes, nested 20-step graph, retained scroll, pending-parameter gates | Physical touch-device behavior is not established by emulated viewport trials |
| Images, measurements and honest timing | Real CPU previews; numbered objects and independently checked Object→Label mapping; photo/2D/negative/intermediate results | Squared units and zoom verified in round 11; deployment measurement precision and target timing need their own calibration |
| Exact lightweight C++ export | Nine-program native matrix plus two actually downloaded browser ZIPs compiled; three independent archive/path checks | Known cross-build intermediate area and EXIF decoder limits remain documented |
| Consistent family/AI state | Rounds 04–12 lifecycle, provenance, annotation/pending-edit guards, immutable batch/cancel/retry, stale result rejection | Final regression and 18 rapid-reopen trials passed |
| White, readable UI | Actual standalone Chrome desktop, 1024×768 and 390×844 checks; prior clipping fixed | Zoom, consolidated labeling and final touch-pan review passed |

## Verification boundary

Current suites pass **55 Python tests** and **34 JavaScript tests**. AI browser trials use
explicitly intercepted fixture responses. They prove request/state behavior, not the
model's ability to recognize objects or propose useful transforms. Actual provider-payload
tests confirm that all training images are included and validation images are excluded.

Final root browser runs are saved as `artifacts/strict/qa_*-final.json`: family
conversation, validation provenance, pending inspector fields, batch cancellation/retry,
individual box correction, zoom/family boundaries and touch panning all pass. A provenance
harness timeout was diagnosed as clicking before reinspection finished; the script now
waits for the completed analysis layout, and the successful rerun is preserved alongside
failure diagnostics. No application change was needed for that timeout.

The current native run is stored in `artifacts/strict/native-timeline-parity.json`. Its
utility case has the previously documented intermediate area difference: 876.719 mm²
native versus 878.321 mm² in Python, due to one mask pixel after cross-build resize
rounding. Its later empty final mask matches, so final-pixel equality alone is not used
to claim complete parity. No new discrepancy appeared in this rebuild.

No result establishes general detection reliability from a few fitted examples. Existing
challenge failures and measurement-error evidence remain in `TESTING.md`.


Two additional browser downloads were compiled from their actual ZIP contents. The photo
path returned 4 detections and the 2D path returned 2; both had zero final-pixel differences
and matching requested measurements. Configurations matched the captured selected path
exactly. Evidence: `artifacts/strict/browser-export-parity.json`. The photo's 2 px/mm scale
was an arbitrary test input, not a physically established calibration. The new 2D example
reset to pixel units. These runs complement the nine-program matrix; they do not erase
its documented intermediate difference.
