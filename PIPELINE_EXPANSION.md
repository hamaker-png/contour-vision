# Pipeline expansion completion record

The requested local web app is available at http://127.0.0.1:8000/. This record covers
the UI refinements, additional native libraries and confirmation branches. The earlier
workflow redesign is documented separately in `WORKFLOW_REDESIGN.md`.

| Requested result | Implementation and inspected evidence | Status |
|---|---|---|
| Rename timelines to pipelines | Editor headings, buttons, errors, AI copy and downloaded filename use pipeline. Screens in `artifacts/ui-review/r3-*` show the rendered terminology. Internal API/JSON identifiers remain compatible with existing saved projects. | Complete |
| Compact blank horizontal header areas | Navigation shares the top bar; context and execution controls are compact; idle feedback reserves no row; comparison starts collapsed. UI expert measured first desktop card at y293 versus y644, a 351px gain. Tablet and phone layouts reviewed without page-wide horizontal overflow. | Complete |
| Center the circle plus | Inline SVG centered within a 44px circle; circle aligns with preview center. Final desktop and phone measured deltas are 0px. | Complete |
| Have a UI expert review the whole webpage | Dedicated agent reviewed all four screens, dialogs, operation picker, Arrange, labeling and responsive states. Three reports and screenshots in `artifacts/ui-review/`; final focused checks pass. | Complete |
| Add more than image transforms | 23 operations now include connected-region detection, fitted circles, line endpoints, barcode identity and confirmation, with detector-specific measurements and intermediate previews. Served examples, 65 Python tests and 41 JS tests passed. | Complete |
| Add libraries besides OpenCV | CImg 3.5.5 provides real connected components/distance; ZXing-C++ 2.3.0 decodes barcodes. CImg uses a shared native core in builder and exports. Pinned sources/licenses are under `backend/vendor/`; native exports compiled and executed. | Complete |
| Branch pipelines and confirm results | Shared-prefix branches remain editable; Confirm branches creates a new pipeline using primary and supporting detections. Deterministic one-to-one overlap, required supporter count and optional matching decoded text are exposed. Missing references, cycles and repeated aliases are rejected. | Complete |
| Preserve exact CPU C++ export | Export schedules the unique selected dependency closure, including supporting branches. All six added operation types passed native/Python pixel and measurement checks. Actual browser download audit verifies 13 unique operations and appropriate included libraries. | Complete |
| Default personal API key locally, if available | No configured key was available. Remember-on-this-computer defaults on and stores a pasted key locally, separate from projects/exports. Public mode disables stored and environment key fallback. Temporary-key tests pass; no personal/fake key was installed. This fulfills the explicitly optional fallback. | Complete |

## Evidence

- `artifacts/ui-review/UI_REVIEW_ROUND_1.md`, `UI_REVIEW_ROUND_2.md`,
  `UI_REVIEW_FINAL.md`: independent rendered review. Final circle/label and example
  measurements are in `round3-final.json` and `round3-supplement.json`.
- `artifacts/expanded-vision-followup-audit.md`: independent verification that detector
  aliases, barcode naming, confirmation move-impact and repeated source resizing were fixed.
- `artifacts/expanded-native/{regions,distance,circles,lines,barcode,confirmation}/parity.json`:
  six compiled exports with zero final-pixel differences on the checked fixtures.
  Barcode includes additional EAN13, UPCA, Code128 and DataMatrix identity checks.
- `artifacts/expansion-browser/run-1789860838193/report.json` and `bundle-audit.json`:
  real CPU runs, support-draft protection, save/open, selected export and downloaded ZIP.
- `artifacts/vision-examples/`: HTTP execution results and every intermediate image for
  the original internet candy photo and generated QR 2D example.
- Final full suites: `python -m pytest -q` — 65 passed; `node --test tests/*.test.mjs` —
  41 passed. Both frontend entry modules pass Node syntax checking. Two existing
  TestClient dependency deprecation warnings remain.

## Boundaries

Agreement is not a reliability probability: the candy demonstration intentionally loses
one correct primary detection through its weaker support. Bounding-box scores do not
prove mask or measurement accuracy. Use representative, freshly held-out images to assess
the chosen graph. Circle measurements describe fitted disks; lines have no measured area
or width; CImg regions count foreground pixels including the effect of holes, while contour
area uses external contour geometry. Pixel-to-unit calibration must match the object plane.

The native checks are Windows x64 with native OpenCV 4.12 and builder OpenCV 5.0. Different
OpenCV builds can change boundaries and rounded measurements. Local timings and heuristic
target estimates are not deployment benchmarks. No physical handset or live OpenAI model
was tested. The app remains a local single-user server; `CONTOUR_PUBLIC=1` changes key
handling and is not a complete public-hosting configuration. See README for setup and export.
