# Verification record

The transform explorer was verified with downloaded internet images, backend/API tests,
JavaScript graph-state tests, compiled C++ exports and actual browser interactions.
Sources and licensing notes are in [examples/SOURCES.md](examples/SOURCES.md).

## Public-release pass — September 20, 2026

The local suite passes **139 Python tests and 48 JavaScript tests**. Added coverage
checks public host/origin rules, bounded request admission, key isolation, sanitized
errors, cancellation ownership and the single-process launcher. GitHub Actions also
runs the suite on Linux and builds/runs the production container.

Browser review covers 1280, 1100, 768, 393 and 320 px widths and a 200%-equivalent
short viewport. It verifies readable operation titles, connected branch arrows,
mobile menu dismissal, modal scroll locking, selected-step visibility, remembered
horizontal position, and consistent export selection through target editing.
The public-mode server was exercised without a key under its actual content security
policy, including all-image execution and label-canvas zoom. Hosted processing and
key-transit copy identify the server explicitly. Live OpenAI calls were not made.

Local review logs and screenshots are retained under `artifacts/public-review/`
(excluded from source control). CI results are available in the repository's
Actions tab. The historical object-pack and native-export evidence below retains
its original scope and counts.

## Offline object-tree pack — September 20, 2026

The current suite passes **129 Python tests and 48 JavaScript tests**. The 20 object
trees add four photo families and 16 generated 2D families, each with two labeled
positive practice images and one empty/distractor negative. All images are training
examples, and generated silhouettes are clearly distinguished from photographs.

`scripts/check_object_examples.py` exercised the live local API: **60 image cases and
159 branch executions**, with every intermediate step successful. Each recommended
path matches all supplied targets with no false positives or misses; alternatives
are permitted to expose weaker approaches. This is fixture fit, not a deployment
accuracy estimate. The same script exports each selected C++ closure and creates
20 saved projects with embedded images. Results, per-stage previews, source credits,
projects and ZIPs are under `artifacts/object-examples/`.

Twenty parametrized Python cases independently exercise the real CPU engine and
validate/export every alternative's typed dependency closure; a catalog test enforces
20 distinct trees, three labeled samples each, and real branch relationships. Suite
logs are `artifacts/object-examples-python-tests.txt` and
`artifacts/object-examples-js-tests.txt`.

Browser checks selected all 20 trees and ran all 60 images without an API key or
provider requests. They also covered desktop/phone layouts, failed partial loads,
stale responses, view resets and the selected pipeline's measurement settings.
Save/Open now preserves the chosen pipeline and step; packaged projects open their
recommended starting pipeline. Three JavaScript regressions cover saved selections,
inherited steps, and safe fallback for older or stale projects.
Browser replay confirmed all three persistence paths; the resolved review and
screenshots are in `artifacts/object-examples/browser-qa/`.

`scripts/check_object_example_exports.py` compiled the actual API ZIPs for solder
pads, elongated tablets and washers. All nine image cases matched final preview
pixels exactly, with matching measurements across 15 stages and correct shared
dependency order. The 19 positive targets had no extra or missed detections.
Reports, configurations, binary hashes and output images are retained in
`artifacts/object-example-native/`. These checks cover the tested build versions
and fixtures, not all platform/compiler combinations.

The earlier checkpoints below retain their original counts and scope.

## Earlier critique-cycle checkpoint — September 19–20, 2026

That checkpoint passed **108 Python tests and 45 JavaScript tests**. Two existing
Starlette/TestClient deprecation warnings remain. Logs are in
`artifacts/night-python-tests.txt` and `artifacts/night-js-tests.txt`.
The app has 30 allowlisted CPU operations and 11 photo/2D teaching examples.
The full change and critique record is [NIGHT_IMPROVEMENTS.md](NIGHT_IMPROVEMENTS.md).

| Evidence | Scope and observed result |
|---|---|
| Six fixed photo/2D families | 110 primary cases, 276 total graph executions; preserve difficult lighting, scale, occlusion and distractor failures |
| Separately captured apple photographs | Frozen preset: 2 TP, 0 FP/FN on two photos; no tuning |
| Separately captured tennis photographs | Frozen preset: 1 TP, 1 FN, 0 FP on two photos; no tuning |
| Analytic optimization families | Separate training/validation seeds for local detail, lines, circles and holed parts; geometry checked separately from box counts |
| Added-operation native exports | 13 fresh compiled configurations pass final pixels, measurement fields and dependency order; four extra barcode formats also pass |
| Seven new transforms | 17 image inputs each, 119/119 identical outputs on the tested Python/native builds |
| Original-operation native exports | Nine rebuilt configurations: eight strict matches, one exact documented OpenCV resize/intermediate-area difference; all final pixels match |
| Classic fixed-strategy exports | Ten rebuilt programs match detector counts, boxes and measurements, including calibration and selected fields; missing-file handling passes |
| Image decoding | 90 files × three native programs = 270/270; exact decoded color, masks and measurements, including all eight EXIF orientations and both TIFF byte orders |
| Malformed/oversized inputs | 185 metadata/container plus 178 dimension cases; 48 valid orientation cases match; invalid TIFF interpretation differences recorded separately |
| Actual browser download | Compiled the unchanged downloaded ZIP; exact selected graph, final/preview pixels and all measurements match; replay on 11 previously sealed circle scenes also passes |
| Live HTTP examples | All 11 examples, 27 pipelines; intermediate outputs, shared dependency totals and supplied hardware-ratio estimates checked |
| Native memory | On one 58-operation, eight-pipeline fixture: 44.97 MiB peak versus 297.53 MiB retaining control, identical results; no speedup claim |

These rows describe different kinds of evidence and must not be combined into one
accuracy percentage. Variations of the same source photograph are dependent stress tests.
The independent photographs are too few to estimate deployment reliability. Box matching
does not establish pixel segmentation, physical metrology or barcode identity accuracy.

The six-family matrix retains every primary failure below (TP / FP / FN):

| Family | Cases | Failure conditions |
|---|---:|---|
| Red candies | 20 | Color removed 0/0/4; similar-color disk 4/1/0; occlusion against full-object labels 3/0/1 |
| Green shapes | 18 | Color removed 0/0/2; tennis-ball confuser 0/1/0 |
| Coins | 18 | Severe dimming 17/0/7; uneven light 23/0/1; quarter resolution 16/3/8; candy confuser 0/3/0 |
| Red apple | 18 | Color removed 0/0/1 |
| Tennis ball | 18 | Color removed 0/0/1 |
| Horse silhouette | 18 | No error in this bounded derived set |

On the separate tennis photograph that failed, the foreground survives the color mask
but is rejected by the frozen minimum-area filter: 13.14% image area versus its 15% cutoff.
This post-hoc diagnosis did not change the preset or the recorded outcome.

Reproduction and evidence:

- `scripts/check_image_families.py` → `artifacts/replay-fixed-family-matrix/report.json`.
- `scripts/check_extended_native.py` → `artifacts/expanded-native/latest-run.json`.
- `scripts/check_native_variability.py` → `artifacts/replay-native-variability/`.
- `scripts/check_native_image_loading.py` generates and compiles its own fixtures/programs.
  Final independent evidence is `artifacts/night-review/vision/image-loading/cycle5-final/`.
- `scripts/check_native_loader_bounds.py` uses the compiled grayscale/gamma export and
  creates a new evidence directory per run. The recorded 363-case run is
  `artifacts/native-loader-bounds/20260920T023706.893685Z/report.json`.
- `scripts/check_final_browser_export.py` compiles the actual saved browser download,
  with its captured POST and project in `artifacts/night-final-browser/`.
- `artifacts/native-memory/README.md` describes the measured controlled comparison.
  `scripts/check_native_memory.py` reproduces it on Windows into a fresh directory.
  The final-loader replay at `artifacts/native-memory-replays/20260920T024742.793236Z/`
  measured 45.28 versus 297.53 MiB with identical results (84.78% reduction on this fixture).
- Independent reviews, source/license manifests, sealed labels, failed trials and
  screenshots are retained under `artifacts/night-review/`.

Browser critique verified Focus/Compare navigation, branch/support links, reordered steps,
draft retention, optimization alternatives, graph-capacity rejection without partial edits,
cancelled/stale requests, Save/Open and Undo/Redo. Reencoding an image without changing
decoded pixels does not make locally optimized training data appear unseen. Desktop
1424×905 and phone emulation 393×852 finish without horizontal page overflow or browser
errors. These are browser-emulation checks, not tests on a physical phone.

No personal OpenAI API key was available. Provider payloads, errors, cancellation,
training-only evidence and state transitions were tested with doubles. Live AI proposal
quality and real API cost/latency remain unverified. CPU search and native execution
tests use real processing. Search/timing budgets stop between native calls and are not
hard real-time guarantees. Target-hardware estimates still require device benchmarking.

The native loader applies supported EXIF orientation explicitly and rejects images over
24 MP before pixel decoding, with a second check after decoding. The tiny oversized-header
fixtures peaked at 4.60 MiB in the recorded bounded run. Malformed TIFF tags may be
accepted differently by Pillow and OpenCV: the 27 interpretation differences are retained,
not mislabeled as valid-image parity. The older cross-OpenCV resize-rounding exception
is detailed below and remains unresolved.

The final JPEG color-mode audit checks 18 further files: RGB baseline/progressive with
subsampling 0/1/2 at qualities 50/95, progressive grayscale, and CMYK. The 14 ordinary
RGB/grayscale files decode pixel-exactly. Four CMYK files initially exposed a one-level
color difference in most channels. Both runtimes now reject CMYK/YCCK JPEG with an
explicit request to convert to RGB. After that guard, the 270-case loader matrix and
363-case bounds suite passed again. Before/after evidence is in
`artifacts/night-review/vision/jpeg-mode-parity/`; final bounds results are in
`artifacts/native-loader-bounds/20260920T025623.695798Z/`.

## Earlier pipeline and native-library expansion checkpoint

The expansion retains the earlier workflow checks and adds CImg distance/components,
OpenCV circle/line detection, ZXing identity decoding and graph confirmation. Earlier
checkpoint: **65 Python tests and 41 JavaScript tests passed**. New tests exercise real
native libraries, holes and wide labels, endpoint geometry, Unicode QR text, one-to-one
confirmation, empty/failed support, cycle/reference rejection, dependency costs, alias
rejection, source-resize caching, graph moves and public-mode key isolation.

`scripts/check_extended_native.py` compiled six actual export bundles and compared final
pixels, detector measurements and dependency order with Python. All six passed with
zero final-pixel differences on those fixtures. Barcode identity was additionally checked
for EAN13, UPCA, Code128 and DataMatrix; all four match, including format spelling.
Per-case reports are in `artifacts/expanded-native/*/parity.json`. These six native
executables are about 6.7–7.2 MB on this Windows x64 setup. Native timings are single-run
smoke measurements, not target-hardware benchmarks. The earlier OpenCV cross-version
rounding limitation below still applies to other images/builds.

The UI expert reviewed all four screens, dialogs and responsive layouts in standalone
Chrome. The final review verifies exact circle/plus centering on desktop and phone,
visible label-completion/Save controls, readable detector parameters, real confirmation
results and QR text. Desktop first-card position improved by 351 pixels relative to its
recorded baseline. Reports and screenshots are under `artifacts/ui-review/`.

`scripts/qa_pipeline_expansion.mjs` exercised the real app in standalone Chrome: a pending
support edit blocks confirmation export, reset restores committed state, save/open retains
support IDs, the restored graph executes, validation selects the current confirmation,
and the browser downloads its ZIP. `artifacts/expansion-browser/run-1789860838193/`
contains the successful report, screenshot, project, request and downloaded bundle.
Its bundle audit verifies all 13 unique required operations, selected confirmation final,
and inclusion of CImg without the unneeded ZXing library.

The served-example check saves every intermediate in `artifacts/vision-examples/`:
the original internet candy photograph yields 4 correct primary objects, 8 supporting
regions, and 3 confirmed objects (one missed target). The UI explicitly explains the
recall loss. Direct and grayscale QR pipelines both decode `Contour sample 42` from an
explicitly generated 2D graphic. These observations do not establish general reliability.

No personal API key was available. Local persistence/public-mode behavior was tested with
isolated temporary fake keys; no fake or real key was installed in the app. Live model
quality remains unverified. See [PIPELINE_EXPANSION.md](PIPELINE_EXPANSION.md) for the
requirement-by-requirement completion record.

## Earlier strict workflow redesign

Checkpoint 2026-09-19: **55 Python tests** (`python -m pytest -q`) and **34 JavaScript
tests** (`node --test tests/*.test.mjs`) pass. The earlier counts below describe the
previous explorer baseline. Two dependency deprecation warnings remain in TestClient.

The new strict critic uses installed **standalone Chrome 153**, explicitly foregrounded,
with its own review tab and project-local browser profile. It does not use the Codex
in-app browser. Reports are preserved at `artifacts/strict/strict-round-01.md` through
`strict-round-12.md`. All twelve review cycles are complete; the final critic accepts
local handoff. The redesign's scope and ledger are in `WORKFLOW_REDESIGN.md`.

The final seven-scenario root Chrome regression passed at 2026-09-19 22:30 UTC. Results
are `artifacts/strict/qa_*-final.json`, covering family conversation, provenance, pending
inspector fields, batch cancellation/retry, box correction, zoom/family boundaries and
touch panning. The provenance harness initially used still-visible old questions as its
reinspection completion signal; waiting for the completed analysis layout fixed its
premature click. Diagnostics and the successful rerun are both preserved.

Independent round12 verifies twelve direct Pan/Draw/save behaviors and eighteen rapid
close/reopen trials after fixing a reproduced loading race. Its baseline failure is
preserved with the successful retest. Final scores are 8.8 / 8.4 / 8.4 / 8.3; no critical
acceptance gates remain. Touch emulation is actual browser-event evidence, not a test
on a physical handset.

Actual browser evidence now covers clean multi-image intake, immediate target definition,
honest missing-key setup, typed sequence rearrangement by mouse and keyboard, independent
branch copies, and image-only save/open. Controlled provider-response integration trials
cover retained clarification answers, saved discovery, cancelled stale requests, preserved
edits during a pending Open, aggregate answer budgets and upload access during AI waits.
Those fixtures prove application state behavior, **not real model analysis quality**.

`scripts/qa_family_conversation.mjs` and `scripts/qa_validation_provenance.mjs` use the
existing standalone Chrome debugging session on port 9223 and the root review tab recorded
in `artifacts/strict/root-tab.json`. They explicitly intercept AI responses, save labeled
evidence and clear interception afterward. They must not run concurrently with the critic's
foreground browser actions. Normal local image validation and execution remain real.

Cancellation tests exercise the actual ASGI body-buffering middleware, skip disconnected
queued jobs and assert that even repeated raw task cancellation cannot release the CPU
semaphore until its native worker exits. A native operation is interrupted only at its
next safe boundary; cancellation is not a claim that an already-submitted AI request was
never received or billed by the provider.

The later strict rounds add real Chrome evidence for compact nested branches, a 20-step
path, stable drag targets, phone/compact-desktop controls, in-flight parameter/name edits,
AI-exposure provenance, per-image progress, cancellation, remaining-image retries and
failed-score exclusion. Round09 verifies photo/2D/negative/intermediate-output review and
individual box correction; its pending-coordinate and unnumbered-detection findings led
to the next fixes. See `STRICT_WORKFLOW_REVIEW.md` for current completion status.

`scripts/qa_pending_export.mjs` downloads actual photo and 2D ZIPs through Chrome;
`scripts/check_browser_exports.py` builds those files and checks their configuration,
final pixels and measurements against Python. Both actual downloads pass: 4 photo
detections and 2 graphic detections, zero final-pixel differences and matching measurements.
The photo's 2 px/mm calibration is a test input, not a measured physical reference.
The independent graphic resets to pixel units. Evidence: `artifacts/strict/browser-export-parity.json`.

## Editable timeline verification

`python -m pytest -q`: **45 passed**.
`node --test tests/workflow.test.mjs tests/evaluation.test.mjs`: **15 passed**.
JavaScript syntax checks passed.
HTTP checks confirm the explorer, operation catalog and JavaScript modules are served
at the existing local URL with the correct module content types.

The new checks cover actual changes in pixels after reordering, explicit image-kind
failures and blocked descendants, independent branch execution, live shared prefixes,
cache reuse, graph cycles/dangling forks/duplicate nodes, invalid parameter rejection,
physical measurements and original RGB, target-estimate direction and missing data,
short remapped draft IDs, stale selections, and revision guards for late responses.
AI tests verify actual executed preview input and exclusion of validation images.
Workspace import validates graph models and decodes image payloads before accepting them.

`python scripts/benchmark_timelines.py` runs the exact editable preset graphs with no
automatic tuning and saves all intermediate PNGs and result JSON in `artifacts/timelines/`.

| Input | Timeline | Objects | Labeled image F1 |
|---|---|---:|---:|
| Red candy photograph | Red hue + contours | 4 | 1.000 |
| Red candy photograph | Dark foreground | 8 | 0.500 |
| Red candy photograph | Edge contours | 7 | 0.364 |
| Flat 2D green graphic | Green hue mask | 2 | 1.000 |
| Flat 2D green graphic | Grayscale silhouette | 2 | 1.000 |
| Flat 2D green graphic | Adaptive silhouette | 3 | 0.800 |
| Coin photograph | Coin edge contours | 22 | 0.957 |
| Coin photograph | Bright coins | 24 | 0.958 |
| Coin photograph | Local bright coins | 24 | 1.000 |

These are fits to three manually labeled examples, not general reliability estimates.
The new graph executes precisely the operations shown; older automatically tuned results
below can differ. Target-hardware ranges are declared heuristics, not measured target
benchmarks. No live OpenAI key was available; graph suggestions were tested with a mocked
provider. Exact edited-timeline C++ export is now implemented and checked below; the
classic exporter is also preserved.

## Critic-driven explorer checks

The independent critic reviews and their detailed category feedback are preserved in
`CRITIC_ITERATION_1.md`, `CRITIC_ITERATION_2.md`, `CRITIC_ITERATION_3.md` and subsequent
round reports. Screenshots and machine-readable evidence are in `artifacts/critic/`.

Browser checks at 906 × 882 and 1280 × 720 covered opening panels, operation availability
for the actual upstream image type, example replacement and undo, keyboard target-box
creation, complete-label confirmation, scoring, relative hardware estimates, retained
comparison/collection expansion, and a successful C++ download through the inspector.
The larger viewport exposed and helped correct grid placement when side panels are
hidden. Existing workspaces were preserved while fresh tabs were used for later reviews.
These are targeted interactions, not a complete accessibility/mobile or browser matrix.
This earlier baseline did not verify the full pointer drawing workflow. Strict round09
subsequently verified real pointer drawing and undo at phone width; later zoom/pan checks
are recorded in the current strict review.

`python scripts/critic_benchmark.py --extra --hard --output artifacts/critic/expanded-benchmark.json` adds the apple, tennis ball and horse
to the original three scenes, using predeclared fixed strategies and manual labels.
The saved `expanded-benchmark.json` contains:

| Group | Cases | TP | FP | FN | Box F1 |
|---|---:|---:|---:|---:|---:|
| Original fitted scenes | 6 | 33 | 0 | 0 | 1.000 |
| Derived brightness, blur, noise, scale and rotation | 36 | 198 | 0 | 0 | 1.000 |
| Synthetic negatives | 18 | 0 | 0 | 0 | Undefined |
| Declared distractor, occlusion and desaturation challenges | 3 | 7 | 1 | 5 | 0.700 |

The three challenges all fail exact-count matching. These failures remain in the report.
Each scene has its own configured task; derived variants do not create independent
same-target validation data. Near-full-frame tennis-ball boxes provide weak segmentation
evidence. The median all-path backend run, repeated timing and preview encoding is about
149 ms per image on this computer, excluding HTTP/browser overhead.

`python scripts/critic_measurements.py` reports shape/parameter errors independently of
bounding boxes in `measurement-evidence.json`. The direct horse silhouette has mask IoU
0.999862; smoothing reduces it to 0.962620 despite retaining box F1 1.000. Eighteen analytic
rectangle cases vary scale, rotation and processing resolution. At max-side 128, worst
length/width errors are 2.52%/7.26%, maximum angle error 0.301 degrees and maximum RGB-channel
error 11. At max-side 1280, worst length/width errors are 1.77%/4.08%, angle error 0.301 degrees
and RGB error zero. Rasterization and contour boundary definitions contribute to these
errors. These are synthetic checks, not physical camera-calibration certification.

`python scripts/critic_http_latency.py` records 15 local HTTP round trips across the first
three scenes: median 182 ms, nearest-rank p95 395 ms in the saved run. JSON encoding,
transfer and decoding are included; browser paint and the 450 ms edit debounce are excluded.
The UI now displays its own request-to-render-call response time (observed 163–165 ms for
the default example), also excluding the next paint and edit debounce. Rapid edit backlog
and large mixed-collection responsiveness have not yet been benchmarked.

## Edited timeline C++ checks

`python scripts/check_timeline_native.py` compiles **9 selected timeline exports** and
checks final pixels and every intermediate contour measurement. The matrix covers all
17 operation kinds, branch-prefix flattening, two measurements in one path, original-source
color, physical calibration and a transform-only hue output. Eight configurations meet
the strict checks. One deliberately sensitive utility sequence has a documented difference:

- Python OpenCV 5.0.0 and native OpenCV 4.12.0 resize 413 × 356 to 200 × 172. One of 103,200
  channel values rounds differently: blue at x173/y27 is native 253 versus Python 254.
- Inversion/HSV/CLAHE amplify this, eventually changing one intermediate contour-mask
  pixel. One area's result is native 876.719 versus Python 878.321 mm²; its other fields
  and all 11 other objects match. Otsu later removes the difference.
- The final mask is empty and identical. Thus final-image equality alone does not imply
  agreement at earlier measurement steps. The checker records the exact observed exception,
  restricted to this fixture, operation, detection, field and values; other mismatches fail.

All nine final images match pixel-for-pixel. Results and the exception are saved in
`artifacts/critic/native-timeline-parity.json`. This is not a claim of universal cross-build
bit-exact parity. The historical grayscale/alpha EXIF limitation was fixed in the later
critique cycles with a shared explicit native orientation loader. That correction now
passes 90 format/orientation cases across three programs, including exact RGB pixels,
masks and measurements. The separate bounded-loader harness passes 48 valid orientation
cases and records malformed TIFF schemas that Pillow and OpenCV interpret differently.
The cross-OpenCV resize-rounding exception above remains.

Statically linked binaries are 5.77–7.20 MB, without Python, an API key or network access.
The latest strict-redesign rerun rebuilt all nine exports and reproduced the same eight
strict matches plus the one documented intermediate area difference. All final pixels
still match. Its evidence is copied to `artifacts/strict/native-timeline-parity.json`.
Single-run local processing times range from 1.81 to 112.39 ms. The high-resolution apple
includes costly resizing; not every example fits a 33 ms frame budget. These measurements
exclude image decode/file I/O and are smoke checks, not a controlled benchmark. The binary
reports actual per-operation times so the intended target hardware can be measured.

## Earlier classic builder image experiments

Labels are manually specified bounding boxes. Matching uses IoU >= 0.5, one detection
per label. These are small training-set fit checks, not estimates of deployment reliability.

| Input | Task | Best tested strategy | Matched / expected | Extra detections |
|---|---|---|---:|---:|
| OpenCV smarties photograph | Red candies, excluding orange/other colors | HSV red wraparound + contours | 4 / 4 | 0 |
| Wikimedia green shapes, flat 2D PNG | Both visible green shapes, including borders | Green HSV mask | 2 / 2 | 0 |
| scikit-image / Brooklyn Museum coin photograph | Separate coins under uneven illumination | Adaptive local threshold | 24 / 24 | 0 |

Weaker candidates were retained for comparison. On the red-candy photo, grayscale and
edge-only baselines each had F1 0.50 because they did not distinguish the requested color.
On the 2D graphic, adaptive thresholding introduced an extra contour (F1 0.80). On the
coin photo, the edge candidate missed one coin (F1 approximately 0.979).

The benchmark saves actual intermediate images, overlays, timings, metrics, and C++
exports in `artifacts/`. Run `python scripts/benchmark.py` to reproduce. Timing varies
with machine load; do not treat preview timings as a promise for another CPU.

## Classic builder automated checks

`python -m pytest -q`: **19 passed**. The tests cover:

- Analytic rectangle length, width, area, RGB, angle, and center.
- Physical-unit calibration and selected output fields.
- Rotated objects and conversion back to original coordinates after resizing.
- Undefined orientation for symmetric objects (null, not an arbitrary angle).
- All three real internet fixtures against independent manual labels.
- Brightness perturbations of the red-candy photo.
- Empty negative images, false positives, and one-to-one label matching.
- Exclusion of held-out data from parameter selection and AI requests.
- Transparent PNG compositing, malformed configuration, and cross-origin rejection.
- C++ ZIP structure and credential-free export.
- Responses API payloads, key errors, and the plan → execution → transform review → export
  sequence using a mocked provider.

The current dependency versions emit two upstream TestClient deprecation warnings;
they do not affect the test results.

## Earlier classic builder browser checks

Verified image loading, baseline experiments, strategy comparison, stage switching,
measurement display, calibrated lengths/areas, invalidation after measurement changes,
and successful C++ download. The UI uses a white background with green and yellow accents.

## Compiled C++ checks

`python scripts/check_native.py`: **10 compiled configurations passed** plus missing-file
error handling. The test actually compiled generated C++17 source and ran Windows x64
executables, comparing every detection box and selected measurement to the Python preview.
This covered HSV, Otsu, adaptive thresholding, Canny, transparent 2D PNGs, all three internet
images, and calibrated/selective measurement output. The native build used OpenCV 4.12.0;
the Python preview used OpenCV 5.0.0. Symmetric objects correctly report a null angle.

The statically linked executables were approximately 7.2 MB each, without Python, a GPU,
model weights, network calls, or an API key. Single-run native processing times in this
check ranged from about 2 to 21 ms depending on the image and strategy; these are local
smoke measurements, not a controlled performance benchmark. Native results are saved to
`artifacts/native-parity.json` and test executables to `artifacts/native/build/`.

## OpenAI integration boundary

No API key was configured during development. The Responses integration and complete
workflow were tested against a mocked provider, **not a live OpenAI model**. Enter a key
in Settings to use real image analysis, clarification questions, planning, and transform review.
