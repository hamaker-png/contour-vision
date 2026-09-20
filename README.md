# Contour — CPU Vision Workbench

A local browser workspace for a human to explore fast classical computer vision.
Compare real intermediate images on left-to-right pipelines, branch alternatives,
reorder operations, edit parameters, and ask AI for editable suggestions. White interface
with restrained green/yellow accents. All image processing runs on the CPU. Start without
an API key using **20 object-test trees**, each with three labeled practice images and
editable branches. Eleven additional photo/2D technique examples remain available.

The main workspace supports transforms, object detectors, measurements and agreement
between branches. Export the selected pipeline as a standalone **C++ program**,
preserving the exact operations, shared steps and supporting branches. Most programs use
C++17; barcode reading uses C++20. No model runs in the exported program.
The previous fixed-strategy builder remains at `/detector`.

## Host from GitHub

The source is [hamaker-png/contour-vision](https://github.com/hamaker-png/contour-vision).
[Deploy this repository on Render](https://render.com/deploy?repo=https://github.com/hamaker-png/contour-vision)
using the included Dockerfile and service blueprint. A Render account is required;
review the selected service plan before deploying. The same Docker image can run on
another container host. See [DEPLOYMENT.md](DEPLOYMENT.md) for configuration and limits.

GitHub Pages serves static files and cannot run this Python/native CPU backend.
The repository is the deployment source; a running service gets its own URL.
Hosted mode disables shared API keys and local key storage. Each visitor can explore
examples without a key or supply a key for that browser page. Uploaded images and AI
keys pass through the hosting server. [Data handling](PRIVACY.md).

## Run locally

Python 3.11+ is needed for the **builder only**. The exported program needs a C++ compiler
and OpenCV development libraries; it does not need Python, an API key, model weights, or a GPU.

Windows (a project-local environment is already set up on this machine):

```powershell
.\.venv\Scripts\python.exe run.py
```

Fresh install, Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

Open [localhost:8000](http://127.0.0.1:8000). Use `--port 8001` for another port or
`--no-browser` to suppress opening a browser. `start.ps1` is also provided on Windows.

## Try 20 ready-made trees without an API key

On **Images**, use **Example trees · no API key** above the upload area. Choose an object
from the **Object tests · photos** or **Object tests · 2D** group. The app loads the images,
target labels, measurement choices and editable branches, opens the intended starting
pipeline, and automatically runs all three images locally. Use **Compare** to see the
alternatives, or select steps to rearrange or adjust them. AI is optional.

The pack covers red candies, coins, apples, tennis balls, washers, hex nuts, bolts,
keys, buttons, bottle caps, pencils, warning triangles, gaskets, packages, leaves,
tablets, connector pins, solder pads, print marks and square fiducials. Each has two
positive images and an empty or distractor-only negative. The 16 flat 2D families are
generated teaching illustrations; the four photo families use existing attributed
photographs and derived rotations. These are practice sets, not independent validation.
Some alternative branches intentionally expose weaker filtering or different measurement
definitions. Physical dimensions still need calibration.

The [pack guide](examples/packs/README.md) lists all starting pipelines.
[Download 20 saved projects](examples/packs/20-object-trees.zip) to extract
and open individually. They include their images and contain no API keys.

CImg operations need the small native bridge. It is already built on this machine.
On a fresh installation, install CMake and a C++17 compiler; `run.py` builds the bridge
once, or run `python scripts/build_vision.py` explicitly. If the compiler is unavailable,
the app starts and explains the missing setup when a CImg operation is selected. The
ZXing-C++ Python binding is installed by `requirements.txt`.

## Guided workspace

1. **Images** starts empty. Upload several PNG/JPEG/WebP images of the same target
   under different conditions. Examples are an explicit option. Uploads are validated
   together before changing the family; duplicate files are skipped. Adding validation
   images to an example keeps its pipeline. Uploading your own training family replaces
   the example; new examples/families reset physical calibration to pixels.
2. **Define target** opens immediately after a training upload. With an API key configured,
   the AI inspects the whole training family automatically, compares common features and
   asks focused questions. Without a key, connect one in AI settings or start manually.
   Answer the questions, describe the target and choose any measurements you need.
3. **Generate approaches** returns a graph draft for review. **Test these approaches**
   adds it and runs the actual transforms. Existing work can be kept while adding alternatives.
   Generation uses all training originals, single-pass results from the whole training family,
   and up to nine intermediate previews from the focused and alternative pipelines. AI produces validated operation data, never executable code.
4. **Compare & edit** shows a compact pipeline outline and one focused strip of real
   intermediate images. Use **Compare** to place up to three selected pipelines together.
   Parent and supporting-method links navigate to their inputs. Select a step
   for parameters, direct move controls and measurements. Use **Arrange steps** for a compact
   ordered list, drag into insertion gaps, or press Alt + arrow keys on a step. Moves that
   break image-type requirements are rejected before execution. Unapplied parameter
   edits survive navigation; apply or reset them before saving or exporting.
5. **Branch from here** creates a live shared prefix. Parent edits affect dependent branches;
   shared steps are edited in the parent. **Make independent copy** in Arrange steps gives a
   branch its own editable prefix. Undo/redo retains graph edits and clarification progress.
6. **Run all images** tests an immutable copy of the same operations and parameters
   across the family, showing results as each image completes. **Cancel run** keeps
   completed results; **Test remaining images** resumes missing or failed images.
   You can inspect another image while the batch continues. No hidden tuning changes your graph. **Filter & measure** consumes a binary mask and reports the
   selected length, width, color, area, orientation and center. Its displayed overlay is a
   preview; downstream operations receive the filtered mask. Physical units need calibration.
7. **Validate & export** makes the chosen path explicit. Label every target in each image;
   a confirmed image with zero boxes is a negative. Results distinguish training, fresh
   held-out validation, reused AI-submitted or locally optimized images, and imports with
   unknown history. Role changes and exact-pixel reencoding do not make used images unseen. Box F1 does not
   certify mask accuracy, measurement precision or general reliability. Each image has
   paired labels/output, numbered detections, missed/extra IDs and measurements. Earlier
   measurement steps are explicitly separated from the final output. Correct individual
   boxes, zoom for small objects, switch between **Draw boxes** and **Pan image**,
   and undo/redo label edits. Pending coordinate edits
   require Update or Reset before Save; saving unchanged labels does not rerun detection.
8. Download the selected pipeline as **C++17**, or **C++20** when it reads barcodes.
   Inherited steps and supporting branch dependencies are included exactly once.
   A sequence ending without a detector is labeled as a transform-only export.
   All 30 operations, multiple measurement steps and physical calibration are supported.
9. **Save project** includes images, labels, operations, target, question answers, completed
   analysis, measurements, hardware and AI exposure history. Image-only projects can also
   be saved. **Open project** validates before replacing the workspace. API keys are excluded.

Project state stays in page memory. Save before closing or refreshing the page.
Use 8-bit RGB/grayscale PNG, JPEG or WebP; transparency is composited over white.
Convert CMYK/YCCK JPEGs to RGB first. The builder and C++ runtime reject those JPEGs
because their decoders otherwise differ at color thresholds.
In **AI settings**, paste a key once and leave **Remember on this computer** checked
to reuse it automatically after reopening the app. The key is stored in the ignored
`.local/settings.json` file, separately from projects and exports. Unchecking the option
removes that saved key; an entered key can still be used for the current page. An
`OPENAI_API_KEY` server environment variable is another local fallback. No personal key
was available during development, so none has been prefilled.
Cancelled or superseded AI responses cannot replace newer work. Image validation and CPU
runs are cancelled when obsolete; a running native operation finishes before its worker
is released. Browser cancellation cannot guarantee that a provider has not already received
an AI request, so submitted-image provenance remains conservative.

Supported operations: resize, Gaussian/median blur, grayscale, RGB/HSV channel extraction,
HSV color masking, CLAHE local contrast, Otsu/fixed/adaptive thresholds, Canny edges,
inversion, morphology open/close, erosion/dilation, and contour filtering/measurement.
Image types are explicit: color, gray, or binary mask. No hidden conversion is inserted.

Additional CPU techniques:

| Operation | Library | Result |
|---|---|---|
| Connected regions | CImg 3.5.5 | Pixel membership, area with holes preserved, visible extents and color |
| Distance to background | CImg 3.5.5 | Fixed-scale distance image for finding thick object centers |
| Detect circles | OpenCV | Fitted circle centers, radii and disk dimensions |
| Detect line segments | OpenCV | Endpoints, length and angle; width and area are undefined |
| Read barcodes & QR | ZXing-C++ 2.3.0 | Decoded text, format and code bounds |
| Confirm with branches | Contour | Primary objects supported by other detector pipelines |
| Fill enclosed holes | OpenCV | Fill background without a four-connected route outside; changes object area |
| Top-hat / black-hat | OpenCV | Small bright/dark features under uneven illumination |
| Sobel gradient | OpenCV + fixed rounding | Absolute X/Y or magnitude, with fixed gain |
| Intensity range mask | OpenCV | Inclusive low/high grayscale selection |
| Morphological gradient | OpenCV | Local bright/dark boundaries |
| Gamma correction | Fixed LUT | Consistent brightness adjustment without image-dependent normalization |

Use **Branch** on a step to share its prefix and try another method below it. Finish
each method with a detector, then use **Confirm branches** to create a confirmation
pipeline. Select that step to choose more supporters, required supporter count and
minimum box overlap (IoU). Matching is one-to-one within each supporting branch;
aliases of the same final detector cannot count as additional votes. Cycles and missing
dependencies are rejected. Confirmation retains the primary geometry and measurements,
and removes rejected objects from the outgoing mask. Its cost includes every required
branch once. A failed support blocks confirmation; an empty successful support means
no matching objects. Confirmation pipelines retain live support links and cannot use
**Make independent copy** until those links are removed.

Agreement is a consistency check, not a reliability probability. Supports must describe
comparable object extents; a barcode label inside a larger object is not a suitable box
overlap match. The **Branch confirmation · photo** example intentionally demonstrates
reduced recall when a weaker method rejects a true candy. **Read a QR code · 2D**
demonstrates native decoding on an explicitly generated graphic.

### CPU timings and target estimates

Every step shows the median of **five warm runs**, using one OpenCV CPU thread with
OpenCL disabled. Timings include the operation's work; Filter & measure also includes
measurement and overlay drawing. Decoding, preview encoding and HTTP transfer are excluded.
Pipeline totals sum medians across the unique dependency closure, including confirmation
supports. Shared operations
are benchmarked once per image across the workspace, and their results are reused by
dependent pipelines.

In **Hardware**, enter the target device, architecture, and a timing basis:

| Basis | Estimated target time | Planning range |
|---|---|---|
| This computer | Measured local time | Actual local repeat range in inspector |
| Clock speed | Local time × local GHz / target GHz | Estimate ÷ 3 to × 3 |
| Known relative speed | Local time / target-to-local speed ratio | Estimate ÷ 2 to × 2 |
| Reference workload | Local time × target reference ms / local reference ms | Estimate ÷ 1.5 to × 1.5 |

Ranges are explicit planning heuristics, **not statistical confidence intervals**. CPU
names, architectures and core counts alone cannot predict throughput. Missing ratios
produce an unknown estimate, not fabricated timings. GHz scaling is especially rough
across architectures. Python/OpenCV preview timings are not compiled C++ benchmarks;
measure the intended binary on the actual target before relying on a frame budget.

Graphs are limited to 8 pipelines, 64 unique operations, 12 new steps per pipeline and
20 steps per complete path. Add Resize first for images above 4.2 MP. Resize is capped
at 2048 pixels on its long side; example presets use 1280. Input limits remain 12 images,
8 MB each, 24 MP per source and 40 MP per batch (with a 60 MB HTTP request limit).

## Classic C++ detector builder

The following workflow is available at `/detector`, separately from custom pipelines:

1. Add up to 12 8-bit PNG/JPEG/WebP images, or load one of the included internet test cases.
   Describe the target and expected lighting, rotation, scale, background, and confusers.
2. Select the information to extract: length, width, area, angle, mean RGB color, center.
   Enter pixels per physical unit only if you have a reference in the same object plane.
3. In **Settings**, enter your OpenAI API key and a vision-capable model ID. The default
   is `gpt-4.1`; availability depends on your account. `OPENAI_API_KEY` can alternatively
   be set in the server environment. The UI key stays in page memory and overrides it.
4. **Analyze images** asks the model to inspect training images, identify important
   features, and ask focused context questions. Answer in the assistant panel.
5. **Generate & test strategies** proposes bounded OpenCV parameter sets, executes them
   locally, and automatically asks the model to compare the actual training transforms.
   This action uses two API calls (planning and transform review), billed to your account.
6. Inspect original, preprocessing, raw mask, cleaned mask, accepted contours, and
   detection overlay. Switch strategies, inspect measurements, or adjust parameters and rerun.
7. **Export C++** downloads `detector.cpp`, `CMakeLists.txt`, `config.json`, and build/run
   instructions. The selected detector and measurement settings are embedded in the source.

Without a key, **Try baseline strategies** runs real local experiments and can export
a working detector. Baselines and bundled examples are explicitly deterministic presets,
not simulated AI responses.

## Classic builder labels, speed, and reliability

Use **Draw target boxes**, label *all* target objects, then check **All targets labeled**.
A checked image with zero boxes is a negative example. Set separate images to held-out
validation. Unlabeled images never contribute to precision/recall/F1.

The engine compares three or four morphology variants per proposal on labeled training
images. Strategies are ranked by training F1, then fewer false positives. With no labeled
training images, proposals retain their original order and remain unscored. Validation
images are never sent to the AI or used to select parameters or rankings. Repeatedly
choosing strategies based on validation results can still overfit that set; use fresh
independent images for final evaluation.

Metrics use greedy one-to-one bounding-box matching at IoU >= 0.5. Undefined precision,
recall, and F1 are shown as a dash, not invented 100% values. The mask separation value
is foreground density inside target boxes minus outside them: a visual diagnostic only.

All detection uses one CPU thread with OpenCL disabled and a maximum processing dimension
of 1280px. Timing is the median of three warm runs per image, including transforms,
measurement, and overlay drawing but excluding decoding and preview encoding. C++ timings
must be measured on the deployment CPU; Python preview timings are not a binary benchmark.

Supported techniques: HSV bands (including red hue wraparound), Otsu thresholding,
adaptive Gaussian thresholding, Canny edges, morphology, and contour filtering by area,
circularity, solidity, aspect ratio, and border contact. Touching objects, texture-only
categories, perspective changes, and occlusion may exceed what these techniques can do.

Measurements use the rotated minimum-area rectangle for length/width and its long-axis
angle modulo 180 degrees. Area is external contour area; holes are **not** subtracted.
Mean RGB averages the filled external contour, so holes/background can affect it. Angle
is reported as null for near-circular/square objects (rectangle aspect ratio <=1.05), which
have no stable long axis. Cropped objects yield visible extents only.
Bounding boxes and centers are always in original image pixels; calibrated length/width
and area use the chosen unit and squared unit. Changing camera distance, resolution,
or object plane invalidates simple scale calibration.

## Export build

Install a C++17 compiler (C++20 for barcode exports), CMake 3.16+,
and OpenCV development libraries. For example,
Debian/Ubuntu: `sudo apt install g++ cmake libopencv-dev`. Windows can use Visual Studio
with vcpkg's `opencv4`, or the official OpenCV SDK. Then, inside the exported ZIP:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
./build/detector image.png
./build/detector --output final.png --preview annotated.png image.png
```

Windows multi-config builds use `build/Release/detector.exe`. Add `-DOpenCV_DIR=...`
to CMake if necessary. Only OpenCV core, imgproc, and imgcodecs are linked. A single
JSON object is emitted for each image. Pipeline exports report final image type/dimensions,
actual per-operation latency, and count, boxes, units and selected measurements for every
measurement step. `--output` saves the final transform; `--preview` saves its overlay when
the last step measures objects. The classic exporter uses `--output` for an overlay.
The binary runs fully offline. `config.json` is descriptive;
changing it alone does not change the compiled constants.

CImg headers/license and pinned ZXing source/licenses are included only when required
by the selected dependency closure. No dependency download occurs during the exported
build. CImg uses the same core implementation in the builder bridge and exported source.

## Optimize a selected pipeline

Use **Optimize selected** after labeling every training image, including empty negatives.
The current pipeline stays unchanged. Local search works without a key; with OpenAI
connected, an optional single API call proposes up to three additional structures.
The search tests parameters against the entire training family and preserves the
current pipeline as its baseline. Add any measured candidate explicitly to inspect
its full editable graph. If AI proposals fail, local search can still finish.

Default search: 32 candidates and 20 seconds; finalist benchmarking has a separate
budget of up to 10 seconds. Shared operations use a bounded cache, with no intermediate
PNG encoding during candidate search. Finalists get fresh measurements: one warmup and
three uncached runs per training image. Timing ranges and uncertain/incomplete results
remain visible. Deadlines and cancellation stop between native calls.

Candidates must retain matched targets, not increase the false-positive count on any
training image, and preserve
individual box overlap within 0.02 IoU. Ranking also considers box localization so that
identical counts do not hide worse geometry. A recommendation needs a quality improvement
or at least 10% median speed improvement with separated paired timing ranges on every
training image. These are training checks. Validate on new independent images and check
object dimensions/masks separately; box agreement does not certify measurement accuracy.

Circle voting has an additional work bound: at most 262,144 input pixels, 25,000 Canny
edges, and edge count × maximum radius at most 500,000. Use Resize with max side 512,
reduce the radius or denoise when the step asks. Contours/lines are capped at 1,000,
circles at 256, and confirmation at 250,000 object-pair comparisons. These limits keep
experiments manageable; they are not a hard per-operation latency guarantee.

## Privacy and implementation

The server binds to loopback only and rejects cross-origin requests. Keys are never
logged, sent to another provider, or put in exports. Optional local key storage is a
plain local settings file protected by the operating system's account permissions;
it is not an encrypted credential vault. Training images are sent to OpenAI for enabled automatic inspection after upload or
explicit AI actions, with Responses `store: false`. This flag does
not override OpenAI's account-level data retention policies. Images/results are in memory;
refreshing the page resets the workspace. Save/open JSON preserves custom workspaces;
C++ exports preserve the selected executable sequence and measurement settings.

The AI returns schema-validated configuration, never executable source. The exporter uses
a fixed C++ template. Input is limited to supported algorithms and bounded parameters.
The backend enforces image size, pixel-count, and batch limits. AI timeout, refused
requests, invalid keys, and rate limits are surfaced without leaking credentials.

Implementation: `backend/timelines.py` (typed graph validation),
`backend/graph_execution.py` (dependency execution and timing),
`backend/vision_ops.py` / `backend/vendor/cimg_ops.hpp` (additional native operations),
`backend/timeline_ai.py` (image-grounded graph drafts), `static/explorer.js` (editor),
`static/workflow.mjs` (immutable graph edits), `backend/engine.py` (classic OpenCV), `backend/ai.py` (Responses API),
`backend/timeline_exporter.py`, `backend/graph_exporter.py` and C++ templates (pipeline export),
`backend/detector.cpp.in` (classic export runtime), `backend/app.py` (FastAPI), `static/` (plain JS/CSS).
No frontend build system is required.

For future hosting, the frontend and JSON APIs already use the same origin. The Python
backend with native OpenCV must run on a server/container; this is not a static-only site.
The current loopback binding and localhost/origin restrictions intentionally support the
requested local setup. Public deployment needs a separate hosting configuration with
authentication, per-user resource limits and origin/host configuration.
Set `CONTOUR_PUBLIC=1` before a future shared deployment to disable saved-key use,
environment-key fallback and local key storage. Remove `.local/settings.json` from any
deployment copy. This flag changes key handling only; it does not enable public hosting.

The API integration follows OpenAI's official [image input guide](https://developers.openai.com/api/docs/guides/images-vision)
and [structured output guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/*.test.mjs
.\.venv\Scripts\python.exe scripts/benchmark_timelines.py
.\.venv\Scripts\python.exe scripts/benchmark.py
```

The pipeline benchmark saves every intermediate preview, step timing, graph summary and
measurement in `artifacts/timelines/`. The classic image benchmark creates overlays, per-strategy metrics, and example C++ ZIPs in
`artifacts/`. Internet fixtures and attribution are in [examples/SOURCES.md](examples/SOURCES.md).
Tests cover the real internet photos and flat 2D graphic, known geometric measurements,
scale/rotation, brightness perturbations, negative examples, train/validation isolation,
request validation, API payloads/errors with a mocked provider, and export structure.
Live OpenAI calls require the user's API key and are separate from these offline tests.

For optional native export checks on a Windows machine without a C++ SDK, the project-local
`scripts/setup_native.py` can build a minimal OpenCV from its official source using portable
Zig, CMake, and Ninja installed via `pip install ziglang cmake ninja`. It uses two build jobs,
does not change system PATH, and keeps tools in `.venv/` and `.tools/`.

After that build, `python scripts/check_native.py` compiles the actual exported source
and compares C++ detection boxes and measurements to the builder on the internet fixtures.
`python scripts/check_timeline_native.py` checks the edited-timeline exporter, including
final pixels, the original 17 operation kinds, inherited steps and repeated measurements. Detailed
verification and limitations are recorded in [TESTING.md](TESTING.md).

`python scripts/check_extended_native.py` compiles 13 added-operation/confirmation exports and
compares pixels, measurements and dependency order with the builder. While the app is
running, `python scripts/check_vision_examples.py` exercises the new examples through
HTTP and saves their intermediate images. See [PIPELINE_EXPANSION.md](PIPELINE_EXPANSION.md)
for the UI review and expansion evidence. Internal JSON/API names such as `timelines`
are retained for saved-project compatibility; the interface calls them pipelines.

For the latest critique cycles, dataset protocols, native parity, resource benchmarks and
known failures, see [NIGHT_IMPROVEMENTS.md](NIGHT_IMPROVEMENTS.md). Reproduce the three
analytic teaching examples with `python scripts/build_classical_examples.py`.

`python scripts/check_image_families.py` replays 110 fixed-preset primary cases across
six photo/2D families, preserving failures. After building the added-operation exports,
`python scripts/check_native_variability.py` compares seven transforms on 17 images
(119 checks). These derived images are stress tests, not independent photographs.
`python scripts/check_native_image_loading.py` builds three programs and tests 90 image
format/orientation cases. `python scripts/check_native_loader_bounds.py` separately
checks bounded malformed metadata and oversized headers against the compiled gamma export.
`python scripts/check_native_memory.py` rebuilds the 58-operation retaining/released
comparison on Windows, with monitored process limits and a fresh output directory.

Regenerate the offline object pack with `scripts/build_object_examples_photos.py`,
`scripts/build_object_examples_a.py` and `scripts/build_object_examples_b.py` (run each
with Python). With the server running, `python scripts/check_object_examples.py` tests
all 60 images and 159 branch executions, saves intermediate previews and exports, and
recreates the saved-project ZIP. `tests/test_object_examples.py` checks target detection,
negative rejection, typed export closures and the 20-tree catalog.
