# Contour review and improvement record

Four independent critic iterations completed. The early-stop condition was **at least
7.5 in every category**, rather than an average. Iteration 4 met that condition, so a
fifth iteration was unnecessary. These are qualitative engineering judgments supported
by the evidence below, not statistically calibrated product scores.

The requested anchors were retained: **10** means exceptional Apple-level functionality
and polish; **7** means good enough for regular use; **5** means sometimes helpful.
The assessed product is a human-guided workbench for relatively simple CPU computer
vision tasks, including 2D graphics. The scores do not certify arbitrary object detection.

| Iteration | Usability | Aesthetics | Speed | Accuracy | Detailed feedback |
|---|---:|---:|---:|---:|---|
| 1 | 5.5 | 6.0 | 6.5 | 6.0 | [Full review](CRITIC_ITERATION_1.md) |
| 2 | 7.0 | 7.2 | 7.0 | 6.2 | [Full review](CRITIC_ITERATION_2.md) |
| 3 | 7.6 | 7.5 | 7.2 | 7.2 | [Full review](CRITIC_ITERATION_3.md) |
| 4 | 7.8 | 7.5 | 7.6 | 7.5 | [Full review](CRITIC_ITERATION_4.md) |

Each linked review contains the evidence boundary, reasons for each score, specific
defects, prioritized improvements, and acceptance checks. The critic reviewed source,
rendered screenshots and test artifacts. Browser interactions were performed by the
implementation agent and identified as supplied observations, rather than represented
as independent critic interactions. Reports from earlier rounds describe the app as it
existed at that point and intentionally retain issues subsequently fixed.

## Improvements between reviews

After iteration 1, the timeline became the main full-width work surface. Images and
inspector panels can be opened when needed; smaller screens use drawers. Source and
transform cards align, headings and filenames remain readable, and branches identify
their parent and fork. A result overview exposes final thumbnails, counts and timings.
The operation picker explains the actual input type and disables incompatible transforms.
Undo restores the full workspace, and hardware/name-only changes reuse computed images.

After iteration 2, users gained target labeling directly in the explorer, with both
pointer drawing and keyboard percentage inputs. Confirmed empty labels represent a
negative image. Collection evaluation separates training from validation and explicitly
counts failed, untested and unlabeled samples. AI and hardware have direct header controls.
Example loading replaces the whole task workspace as one undoable action. Three additional
internet examples broadened testing to a large apple photograph, a tennis ball and an
irregular horse silhouette. Challenge failures were retained rather than tuned away.

After iteration 3, the inspector gained export of the exact selected C++17 timeline,
including inherited steps in order and all 17 supported operations. It reports actual
native per-operation timings and every measurement step. Compiled checks covered nine
programs and exposed a small cross-build intermediate rounding difference, documented
below. Separate shape-fidelity and geometric/color error reports strengthened the accuracy
evidence beyond bounding-box matching. HTTP timing and browser response timing were added.
Nested collection expansion now persists. A 1280 × 720 browser check found and corrected
desktop grid placement when side panels were hidden.

## Verification and practical limits

- **45 Python tests and 15 JavaScript tests pass.** Real browser checks cover example
  loading/undo, keyboard labeling/scoring, type-aware operation controls, hardware changes,
  persistent collection expansion and downloading a selected C++ timeline. Screenshots
  include 906 × 882 and 1280 × 720 viewports.
- **Six fitted scenes:** 33 matched targets, zero extra/missed. **Thirty-six derived
  variants:** 198 matched, zero extra/missed. **Eighteen synthetic negatives:** zero false
  positives, undefined F1. **Three declared challenges:** 7 matched, 1 extra, 5 missed,
  aggregate box F1 **0.700**. Each scene uses its own configured task; these are not a
  frozen detector's independent same-target validation set.
- **Horse mask fidelity:** direct silhouette IoU **0.999862**, smoothed silhouette
  **0.962620**, despite both having perfect box scores. This demonstrates that a useful
  transformation must preserve the feature of interest, not merely its outer box.
- **Measurement tradeoffs:** eighteen analytic rotated/resized rectangles show worst
  length/width errors of **2.52%/7.26%** at max-side128 and **1.77%/4.08%** at max-side1280.
  Low resolution also changes mean color. Raster geometry tests do not certify real-camera
  calibration, perspective, or physical measurement accuracy.
- **Latency:** saved local HTTP runs have a **182 ms median** and **395 ms nearest-rank
  p95**, including JSON/transfer but excluding browser paint and the 450 ms edit debounce.
  Browser response values were about163–165 ms on the default example, measured through
  the render call, not the next paint. Rapid-edit backlog and large collection latency
  remain unmeasured. Target-hardware estimates remain explicit planning heuristics.
- **Native execution:** nine selected paths compiled to roughly **5.77–7.20 MB** static
  Windows binaries. All final images matched; eight also passed strict intermediate
  measurement checks. One utility path differed in a single contour area by **1.602 mm²**
  (876.719 versus878.321) because one resize channel rounded differently between Python
  OpenCV5.0.0 and native4.12.0. Its final empty mask hides this intermediate difference.
  The test records a narrowly bounded exception, not universal bit-exact parity. Local
  single-run native processing ranged **0.96–116.97 ms**; the large apple's resize is costly.
- **AI integration is mocked, not live-model evaluated.** No API key was configured.
  Suggestions, input isolation and errors were tested at the integration boundary.
  Grayscale/alpha EXIF orientation remains an exported-decoder parity limitation.

The most useful next work is individual box correction, larger image previews, a measured
rapid-edit/collection workflow, and a frozen detector tested on independently captured
images of the same target. Full details and acceptance checks remain in the fourth review.

See [TESTING.md](TESTING.md) for reproduction commands and fuller evidence, and
[README.md](README.md) for running and exporting the app. Machine-readable results and
screenshots are in `artifacts/critic/`; image attribution is in
[examples/SOURCES.md](examples/SOURCES.md).
