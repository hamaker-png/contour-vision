# Strict workflow redesign

User confirmation completed before application edits. Work began 2026-09-19 around
16:19 New York time. Hard stop: **2026-09-19 20:30 America/New_York**
(2026-09-20 00:30 UTC). New York is on EDT today; this interpretation was explicitly
communicated before implementation. Check the clock between review cycles and preserve
time for final verification/reporting. Do not extend work beyond the deadline.

The user requests significantly more iterations than the earlier four, stricter critique,
and actual external-browser evidence. Target 10–12 substantive review/fix/test cycles;
do not count status reports or unchanged screenshots as iterations. No score-only early
stop. Each cycle must identify a concrete usability defect, change behavior, and verify
the result against the user journey. Report any remaining gap honestly.

## Product requirements

1. Empty-first image-family intake. Multiple images belong to one intended target task;
   examples are explicit and never silently contaminate a new family.
2. Immediate transition after upload into an AI-guided discovery conversation. The model
   compares all training images, identifies common features/variation, and asks focused
   questions. A missing key has an explicit setup path; no fabricated AI analysis.
3. A clear linear path: Images → Define target → Compare and edit → Validate and export.
   The user can revisit earlier steps without losing their work.
4. Comfortable timeline rearrangement with visible insertion locations, keyboard access,
   type feedback, understandable branch inheritance, and reversible edits.
5. Actual intermediate image previews, promising alternatives, original-source object
   measurements, local CPU timings and honest target estimates remain available.
6. Exact selected sequence exports to lightweight offline C++ with no model/API dependency.
7. Family/AI/draft state stays consistent across edits, cancellation, upload errors,
   validation roles, save/open and undo. No stale suggestion can silently replace newer work.
8. White interface, restrained green/yellow accents, readable controls and responsive layout.

## Evidence and review

The strict critic uses standalone installed Chrome, a dedicated project-local profile,
and CDP at localhost:9223. It uses its own tab and saves independent reports/screenshots
outside the checkout for root to preserve. It must not use the Codex in-app browser.
The root implements changes and runs separate browser regression scenarios. No personal
browser profile is used. Source and unit tests support but do not substitute for task trials.

Critical gates: family is clean after upload; next action is immediately apparent;
AI sees training family only; valid pipeline can be edited/reordered without hidden
breakage; feedback persists and can be corrected; chosen path can be validated/exported.
An unresolved critical journey failure prevents completion regardless of numeric scores.

Live OpenAI calls depend on a configured key. Mocked provider tests will be labeled as
integration tests and never presented as evidence of model quality.

## Iteration ledger

| Cycle | Evidence and defect | Change / verification |
|---|---|---|
| 01 | Strict external Chrome baseline: workflow 3.5, editing 4.0; own uploads mixed with demo images and did not prompt discovery. | Empty-first family intake; atomic batch validation; upload enters Define target; automatic discovery when configured; explicit no-key setup. |
| 02 | Strict Chrome review: workflow 6.4, clarity 7.0; image-only save/open passed, but inspection/generation competed and export implied a detector from Resize alone. | Sequential AI actions and explicit transform-only export status; shared backend type validation rejects incompatible AI paths. |
| 03 | Rearrangement previously broke three child paths by moving HSV into their shared prefix. | Visible insertion gaps, Arrange steps, direct/keyboard moves, dependency preflight and independent branch copies. Strict foreground Chrome review verified dragging, repeated keyboard moves and independent copies; editing score 6.7. A background-tab focus finding was explicitly withdrawn after foreground reproduction. |
| 04 | Controlled provider-response trials in standalone Chrome proved that a third upload loses answered questions, and a pending AI request locks further upload. | Persisted conversation and family-bound discovery; upload releases before AI wait; no silent answer truncation. Strict Chrome trials passed save/open, answer retention, pending edits, late cancellation and stable drag geometry (0 px shift). Workflow 7.3, reliability 6.8. |
| 05 | AI-submitted images could be relabeled as held-out; metadata and intake history had additional races. | Strict foreground Chrome passed mixed corrupt/valid atomicity, duplicates, 12/13-image boundary, reused/unknown provenance, stale drafts, long saved text and cancelled intake. Workflow 7.5, reliability 7.1. Review identified that role Undo hid Redo on the Images screen. |
| 06 | Redo disappeared after cross-screen undo; inherited cards repeated whole prefixes; blocked arrows depended on hover titles. | Strict Chrome confirmed global history, compact expandable shared input, retained independent row scroll, visible type explanations, nested branches and a scrollable 20-step Arrange dialog. Scores 7.7 / 7.5 / 7.6 / 7.1. |
| 07 | Phone upload placed AI below the fold; an incoming preview erased Resize input and focus. | Immediate mobile AI handoff and retained inspector form/name DOM. Independent phone and compact-desktop fixtures verified conversation, controls, raw text, focus and Apply. Scores 7.8 / 7.5 / 7.7 / 7.2. |
| 08 | Whole-family execution had no partial results or Cancel; navigation aborted the batch. | Sequential immutable requests, progress, Cancel, retained completed results and exact remaining-image retry. Independent real CPU trials also verified HTTP-failure score exclusion and stale-edit rejection. Prior visual clipping fixed. Scores 8.0 / 7.7 / 7.7 / 7.4. |
| 09 | Validation summaries hid individual errors; correcting one box required redrawing labels. | Paired original/output review, per-image states, individual box update/delete and local history. Photo/2D/negative/intermediate-output browser trials passed; critic found pending coordinate loss and missing detection identity. Scores 8.1 / 7.8 / 7.7 / 7.6. |
| 10 | Save lost unapplied coordinate edits, and measurements could not be associated with specific detections. | Explicit Update/reset gates; numbered detections, verified Object-to-Label mapping and missed/extra highlights. Pending operation drafts survive navigation; same-ID Open and Undo reset retained DOM. Three independent browser ZIP/config checks plus two root-compiled browser downloads. Scores 8.4 / 8.1 / 8.0 / 7.7. |
| 11 | Small objects were hard to label precisely; duplicate controls competed; area units were ambiguous; adding validation to an example discarded its graph. | Independent 4× touch drawing preserves exact normalized coordinates; held-out additions preserve edited graphs; new families reset calibration; explicit per-value units and consolidated labeling. Eight desktop criteria pass; touch panning defect found. Scores 8.6 / 8.3 / 8.2 / 8.3. |
| 12 | Zoomed touch gestures drew boxes instead of moving the image; rapid close/reopen could leave labeling stuck loading. | Explicit Pan/Draw modes, native touch panning, mouse/pen dragging, secondary-touch cancellation and a dialog-session guard. Independent final review passes all 12 gesture/drawing/save checks and 18 rapid-reopen trials. Failed race baseline and successful retest are preserved. Final scores 8.8 / 8.4 / 8.4 / 8.3; local handoff accepted. |
| CPU cancellation (supporting work) | Browser abort left obsolete CPU work queued; raw asyncio task cancellation could release the worker lock early. | Event-driven disconnect watcher, checkpoints between native calls, retained/shielded worker drain. Five cancellation tests include actual body-buffering middleware, queue skip, one-worker invariant and repeated raw Task.cancel(). Normal execution tests still pass. |

2026-09-19 22:09 UTC checkpoint: 55 Python tests and 34 JavaScript tests pass.
These support current behavior alongside the completed browser lifecycle trials.
No live OpenAI request has been used in this redesign's verification.

Native export regression was rebuilt from current sources: nine executable configurations,
all final output pixels equal; eight strict measurement matches and the same documented
OpenCV-build intermediate area difference in the utility case. Evidence was copied to
`artifacts/strict/native-timeline-parity.json`. No new native discrepancy appeared.

## Completed acceptance

At **2026-09-19 22:30 UTC / 18:30 New York time**, all twelve independent review cycles
and the final seven-scenario standalone Chrome regression had passed, before the hard
deadline. Reports, baseline failures and successful retests are preserved in
`artifacts/strict`. The final critic accepts all eight criteria within their stated scope,
with no unresolved critical gates. A separate factual audit found no unsupported claims.

The final regression covers family conversation, validation provenance, pending inspector
fields, batch execution/cancel/retry, individual label correction, zoom/family boundaries
and touch panning. Its provenance script initially clicked during a still-updating AI
response; it now waits for completed analysis before locating the next control. Failure
diagnostics are retained. The corrected scenario and all remaining scenarios passed.

Controlled AI fixtures do not prove live model quality. Physical phones, physical scale,
representative detection reliability and target timings need deployment-specific validation.
The known cross-build native area exception remains documented. These evidence boundaries
do not leave an unimplemented local-workflow requirement.
