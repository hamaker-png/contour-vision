# Iterative critique and testing

Requested work: improve the app, especially the clunky pipeline tree; add standard
lightweight vision functions; make AI-guided optimization efficient and evidence-based;
test extensively on different image sets. Critique cycles run through 11pm Eastern local
time, September19 (03:00 UTC September20). Initial work began at01:16 UTC.

Three independent review roles covered interaction/visual design, CV accuracy and
image-set testing, and AI optimization/performance. Root owns implementation. Reviews
are written outside the checkout and retained with artifacts after each cycle.

## Cycle 1 — baseline and design

- UI critic inspecting topology navigation, comparison, branch confirmation and editing.
- CV critic proposed bounded morphology, gradients, intensity masks and hole filling;
  obtaining two independently captured held-out apple photographs before inference.
- Optimization critic identified repeated five-run benchmarking/preview encoding during
  search as avoidable; called for a baseline, bounded search, finalist-only benchmarking,
  and provenance for local tuning as well as API submission.
- Implemented first slice: fill holes, top-hat, black-hat, Sobel, intensity range mask,
  morphological gradient and gamma LUT, with allowlisted matching C++ snippets.

The goal remains in progress. Results, failed trials and completion checks will be
recorded as observed; a deadline alone is not proof that a requirement is complete.

## Cycle 2 — interaction and cross-build correctness

The independent UI review measured three pipelines occupying 1,296 vertical pixels.
The editor now has a compact pipeline outline and one focused horizontal strip, with
an explicit comparison view limited to three pipelines. Parent and confirmation links
navigate to the relevant input. Selection, drafts, scroll positions, keyboard focus,
Undo/Redo and branching were tested in the browser. Phone Project/Options disclosures
and a collapsed comparison chooser leave 393 pixels for the image workspace in the
reviewed viewport. A desktop disclosure regression was caught and fixed during review.

Added seven allowlisted operations, for 30 total: hole filling, top-hat, black-hat,
Sobel, intensity range, morphological gradient and gamma. Two new analytic 2D examples
compare global thresholds with local detail extraction; both local paths find all
three known spots, while the global baselines retain their misses/false positive.

An independent 7-operation × 17-image native matrix initially found 1,224 one-level
Sobel differences across seven inputs. The fix uses double precision magnitude and
explicit half-up rounding in both implementations. The rerun passed 119/119 with
identical pixels. This does not erase an older, separately documented OpenCV 5 versus
4.12 resize/intermediate-area difference in the utility pipeline.

## Cycle 3 — optimization, provenance and resource bounds

Optimization preserves an immutable baseline, uses only completely labeled training
images, tests a bounded neighborhood and optional three AI-proposed structures, caches
shared work without preview encoding, then freshly benchmarks finalists. It keeps
quality and speed alternatives. No candidate may lose a baseline-matched object, add
to the false-positive count on an image, or lose more than 0.02 overlap for a matched target.
Equal-count candidates also rank by localization; a gain of at least 0.03 mean truth
box overlap can support a recommendation. Speed recommendations need at least 10%
median improvement and nonoverlapping paired timing ranges on every training image.
These are training diagnostics, not held-out accuracy or physical metrology claims.

The holed-parts development case exposed why counts alone were insufficient: smoothing
preserved F1 but distorted geometry. After the scoring fix, the exact-shape proposal
was retained; new validation layouts gave 10 TP, 0 FP/FN and exact foreground areas.
The circle family retained a rectangle false positive: 10 TP, 1 FP, 0 FN on its fresh
validation set. Both optimized programs compiled and matched Python on 12/12 layouts;
those builds predated the later graph-memory refactor and are labeled accordingly.

AI evidence uses one pass over all training images and at most nine transformed
previews. Invalid experimental paths are recorded instead of blocking useful paths.
Original images are resized/encoded during the CPU phase and reused for the provider
payload. Browser disconnect cancels CPU work between operations and cancels provider
I/O. All of this is tested with provider doubles; no live API key was available.

The provenance ledger tracks AI submission and local tuning by encoded bytes and exact
decoded pixels. Old saved histories migrate to pixel identities; failed decode hashing
can retry; pixel decoding is serialized; image-byte memo entries are retained only
while active or referenced by undo/redo. These changes prevent exact-pixel reencoding or role
changes from presenting used training data as fresh validation.

Stress testing found expensive noisy Hough searches and excessive retained frames.
Circle detection now preflights image/edge/radius work. Confirmation limits candidate
pair comparisons. Contour counts are bounded, and color sampling uses object ROIs.
The 64-operation memory fixture fell from 65 live image arrays to 3, preserving every
encoded preview and result. Exported C++ also releases images/batches after their last
consumer and avoids copying whole support batches for confirmation.

Browser checks passed actual optimization, explicit alternative insertion, stale target
rejection, malformed/server-error recovery, cancel → new search, Escape and keyboard
navigation. Transport fault/race fixtures are explicitly distinguished from real runs.

## Image-set evidence so far

- Six existing internet photo/2D families: 110 predeclared primary cases and 276 total
  fixed-graph executions, including illumination, noise, scale, rotation and negatives.
  Severe dimming, downscaling, cross-family confusers and deliberate candy challenges
  expose failures; the report retains them instead of pooling away differences.
- Two separately captured apple photos, with sources/licenses/labels and the existing
  preset frozen before inference: 2 TP, 0 FP/FN; overlaps about 0.902 and 0.932. These
  two images cannot establish broad reliability; no tuning used them.
- Four analytic optimizer families with separate train/validation seeds, including
  local illumination, lines, circles and holed parts. Shape/measurement evidence is
  reported separately from box counts.

## Cycle 4 — independent photographs, confirmation and provenance

Two tennis photographs from different photographers were downloaded and labeled before
inference, with the existing preset frozen. One passes (box IoU 0.930); the other is a
miss because its object occupies 13.14% of the image, below the preset's 15% minimum-area
filter. The mask itself isolates the ball. No tuning was performed on either image;
the miss remains in the report. Source links, attribution, licenses and hashes are in
`artifacts/night-review/vision/tennis-heldout/sealed-tennis-plan.json`.

The circle/rectangle failure from cycle 3 became development input for a separately
frozen contour-confirmation hypothesis. Eleven new analytic scenes retain all 12 true
circles and remove four false positives across five negatives. These constructed scenes
are not a natural-image reliability estimate. An additional development teaching image
became the eleventh app example: primary 2 TP + 1 FP, confirmed 2 TP + 0 FP, with fitted
circle dimensions preserved. See `artifacts/night-review/vision/circle-confirmation/`.

Actual browser persistence tests confirmed locally tuned image provenance through
Save/Open, refresh, role changes and Undo/Redo. Reencoding the same decoded pixels from
a 16,642-byte PNG to a 2,399-byte PNG remained reused evidence, with zero fresh held-out
images. A later capacity check added alternatives up to eight pipelines, then confirmed
that a rejected extra alternative leaves graph and images unchanged. Optimized prefix
names now clearly distinguish the independent copied prefix from the original.

## Cycle 5 — loader correction and bounded execution

Independent format tests found real native-coordinate mismatches: grayscale JPEG
orientation 6/8, RGB WebP orientation 6 and RGBA PNG orientation 6. The Python builder
rotated these correctly while the exported loader did not. The shared native loader now
decodes once, composites transparency over white and explicitly applies bounded EXIF
orientation for PNG/JPEG/WebP. It stops at PNG IEND and the declared WebP RIFF boundary.
Image dimensions are checked before decoding, using overflow-safe products, and after
decoding before color conversion. Malformed short EXIF errors now produce HTTP 400
instead of an internal error; actual-byte regression tests cover both exception paths.

Final independent verification: **90 cases × three compiled programs, 270/270 passed**,
including identity-color pixels and 179 measured objects. All eight orientations, both
TIFF byte orders, grayscale, alpha and palette transparency are included. The original
four failures and the intermediate fixes remain preserved. A separate adversarial
harness exercises 185 metadata/container cases and 178 tiny oversized/truncated headers.
All 48 valid cases agree; resource/container/error checks pass. Twenty-seven malformed
TIFF interpretation differences remain explicitly recorded. Maximum observed process
memory in that bounded run was 4.60 MiB; this is not a whole-app memory claim.

The 58-operation/eight-pipeline native benchmark measured **44.97 MiB peak working set
versus 297.53 MiB** for a controlled retaining variant: 84.89% less on this fixture.
Both variants produce identical semantic JSON, final pixels, previews and all nine
measurement stages. Single native times were 183.35 and 174.50 ms respectively; no
speedup is claimed. Sources, graph, image and instrumentation are in
`artifacts/native-memory/`, including a report explaining the comparison.
A fresh final-loader rebuild using `scripts/check_native_memory.py` independently
reproduced 45.28 versus 297.53 MiB with identical results. That replay is preserved
under `artifacts/native-memory-replays/20260920T024742.793236Z/`; small working-set
variation between runs is expected, and no throughput conclusion is drawn.

## Final verification audit

- **108 Python tests, 45 JavaScript tests pass**; two existing dependency deprecation
  warnings remain. Real tests cover optimizer baseline protection/localization, caching,
  train/validation isolation, cancellation/draining, graph lifetimes, malformed image
  handling and confirmation work limits.
- Rebuilt all 13 added-operation/confirmation exports. All pass exact final pixels and
  measurement checks, plus EAN13, UPCA, Code128 and DataMatrix identity cases.
- Replayed the seven new native transforms on 17 inputs each: 119/119 identical outputs.
- Rebuilt the original nine pipeline exports: eight strict matches and the one retained
  OpenCV 5/4.12 intermediate-area exception; all final pixels agree.
- Rebuilt ten classic detector exports as well, including calibrated/selective measurements
  and missing-file handling; all native comparisons pass.
- Actual standalone Chrome actions downloaded the selected confirmation ZIP and saved
  the project. Root compiled that unchanged ZIP and verified all three detector steps,
  final mask, preview and exact configuration. The same browser binary passed an
  independent replay of all 11 previously sealed circle scenes and 33 measurement steps.
  This replay checks export parity on existing evidence; it adds no new accuracy data.
- Desktop and phone checks pass. A favicon 404 found during the audit was fixed and a
  fresh reload has no console, JavaScript, HTTP or loading errors. Browser is left on the
  confirmed example. `artifacts/night-final-browser/` contains the actual downloads,
  captured request, screenshots, compiled binary and parity report.
- The six-family matrix was replayed with all failures retained. Current summary and
  commands are in [TESTING.md](TESTING.md); no combined reliability percentage is claimed.
- Final live HTTP checks run all 11 served examples and 27 pipelines, preserve every
  intermediate, verify shared dependency totals and verify the supplied half-speed CPU
  estimate. These check the estimate calculation, not actual hardware prediction accuracy.

Portable reproduction scripts now cover the fixed-family matrix, native variability,
format/orientation matrix, malformed/dimension bounds and actual browser export. Original
reviews, images, sealed labels, licenses and reports are retained in
`artifacts/night-review/`. No live OpenAI request was made without a user key; model
quality remains unverified. CPU timing estimates require benchmarks on the actual target.

The final color-mode audit added baseline/progressive JPEG and subsampling coverage.
Four CMYK JPEGs exposed a one-level native/Pillow color difference. Both runtimes now
reject CMYK/YCCK with a convert-to-RGB message instead of risking different threshold
results. All 14 RGB/grayscale cases remain exact, all four CMYK rejections agree, and
the 270-case matrix plus 363-case bounds suite passed again after this guard. Earlier
accepted-CMYK differences are retained as before-fix evidence. The new two Python
regressions bring the suite to 108 tests. Prior memory and nine-path/ten-classic reports
record their exact pre-guard source hashes; the guard changes JPEG acceptance, not graph
operations or frame lifetimes.

## Closure

The requested review window ended at 03:00 UTC (11pm Eastern local). Final browser
export replay completed at 03:00:39 UTC with all 11 scenes and 33 measurement steps
matching after the CMYK guard. All 13 added-operation exports were also rebuilt with
that guard and passed. The current app is running at http://127.0.0.1:8000/; live malformed
EXIF and CMYK uploads return actionable HTTP 400 errors, with CPU-only health confirmed.
The requested work and bounded critique/test cycles are complete. Known failures,
cross-build limitations and the lack of live AI testing remain explicitly documented.
