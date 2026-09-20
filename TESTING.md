# Testing and validation

Run checks from the repository root with the Python environment described in the
[README](README.md). Python 3.12 is the tested runtime. Native operations also need
the CImg bridge; build it with `python scripts/build_vision.py` if it is not already
available. That build requires CMake and a C++17 compiler.

## Automated tests

```sh
python -m pytest -q
node --test tests/*.test.mjs
```

The September 20, 2026 release passed **140 Python tests and 50 JavaScript tests**.
Coverage includes image operations and measurements, graph dependencies and edits,
training/validation separation, project persistence, stale requests, cancellation,
bounded imports, public host/origin rules, request limits and API-key isolation.
Two upstream Starlette/TestClient deprecation warnings remain in the local environment.

[GitHub Actions](https://github.com/hamaker-png/contour-vision/actions) runs the suites
on Linux and builds and starts the public-mode Docker container. The container smoke
test checks public health, host policy, disabled server keys, non-root execution and
an actual CImg operation. This does not establish a deployed service or production
load capacity; see [DEPLOYMENT.md](DEPLOYMENT.md).

## Example and image checks

Start the local app with `python run.py --no-browser`, then use a second terminal:

```sh
python scripts/check_object_examples.py
python scripts/check_image_families.py
```

The first command checks all **20 object trees, 60 images and 159 branch executions**
through the local API, saves intermediate outputs, and creates project/C++ packages.
Every recommended path matched its supplied targets without false positives or
misses in the recorded run. Alternative paths deliberately include weaker results.
The pack contains four photo families and sixteen generated 2D families; the photo
variations reuse their original capture. [Image sources](examples/SOURCES.md) and
the [example guide](examples/packs/README.md) describe the fixtures.

The fixed-family matrix checks six photo/2D families across **110 primary cases and
276 graph executions**. It includes lighting, noise, scale, rotation, negatives and
confusers. Known failures include desaturated color targets, severely dimmed or small
coins, same-color distractors and partial occlusion. These checks exercise robustness;
they do not establish reliability on independently captured deployment images.

## C++ parity checks

The recorded native checks compare actual compiled exports with Python results:

| Check | Recorded result |
|---|---|
| Selected object trees | 3 programs, 9 images: identical final pixels and matching measurements across 15 stages |
| Expanded operation set | 13 configurations: final pixels, measurement fields and dependency order match; 4 additional barcode formats match |
| Transform variability | 7 transforms on 17 inputs each: 119 identical outputs |
| Original editable pipelines | 9 configurations: all final images match; 8 strict matches and 1 intermediate-area exception described below |
| Classic fixed strategies | 10 programs: matching counts, boxes and selected measurements |
| Image loading | 90 files across 3 programs: 270 matching color/mask/measurement checks |
| Additional JPEG modes | 14 RGB/grayscale cases match; 4 CMYK cases are consistently rejected |

The object-tree, expanded-operation and original-pipeline build scripts currently use
the project-local Windows compiler/OpenCV setup. On Windows, prepare that optional
setup once; it downloads and builds OpenCV 4.12.0 and may take several minutes:

```sh
python -m pip install ziglang cmake ninja
python scripts/setup_native.py
python scripts/check_object_example_exports.py
python scripts/check_extended_native.py
python scripts/check_native_variability.py
python scripts/check_timeline_native.py
```

Run `check_object_examples.py` first to produce the object export inputs, and
`check_extended_native.py` before the variability check. For a system CMake/compiler
and OpenCV development installation, the image-loader check supports:

```sh
python scripts/check_native_image_loading.py --system-toolchain
```

Pass `--opencv-dir` if CMake cannot find OpenCV. This check generates its own inputs
and builds three programs; it needs Pillow with WebP support. Most exports use C++17;
barcode exports require C++20. Build instructions are also included in each export.
Generated reports, previews and binaries go under the ignored `artifacts/` directory.

## Browser checks

The release was exercised in Chrome at desktop and phone-emulated widths from 320
to 1424 pixels, plus a short viewport equivalent to 200% zoom reflow. Checks covered
example loading, Focus/Compare, parameters and reordering, labels and zoom, selected
export persistence, Save/Open, cancellation/retry and public-mode CSP behavior.
An imported 20,000-answer history is rejected without changing the existing project;
ordinary histories and long editable drafts remain usable. These were targeted
browser checks, not a complete accessibility or physical-device test matrix.

## Limits of the evidence

- Exact output equality is specific to the tested builds and fixtures. Python
  OpenCV 5.0.0 and native OpenCV 4.12.0 differ by one resized channel value in one
  sensitive pipeline; later transforms change one intermediate contour area from
  878.321 to 876.719 mm². Its final image still matches. Final-image equality alone
  does not prove intermediate measurement equality.
- Box matching uses IoU >= 0.5 and one detection per label. It does not establish
  mask accuracy, physical calibration or barcode identity. Generated images and
  transformed copies of one photograph are not independent validation captures.
- Timing depends on image size, operations, machine load and build. Target-device
  timings are estimates until measured on that device. Cancellation and search
  budgets are checked between native calls, not hard real-time deadlines.
- OpenAI request construction, errors and state transitions were tested with test
  doubles. No live API key was used; model suggestion quality, cost and latency
  remain unverified. Local image processing and compiled-export checks use real CPU
  implementations.
