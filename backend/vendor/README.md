# Pinned native dependencies

The builder and exported programs use these real CPU libraries. Only dependencies
required by the selected pipeline and its supporting branches are packaged in an export.

## CImg 3.5.5

- Source: [official versioned CImg header](https://github.com/GreycLab/CImg/blob/v.3.5.5/CImg.h).
- Vendored file: `CImg.h`, unmodified upstream source.
- SHA-256: `7f2bac2eed4944a70f9f97682bdf8ce5975e856eb2ad8965cd3a25b7cf2bae28`.
- License: `CImg-LICENSE.txt` (CeCILL-C), included in relevant exports.
- `cimg_ops.hpp` is Contour's shared implementation for connected components and distance
  maps. `cimg_bridge.cpp` exposes it to Python through a small C ABI. C++ exports include
  the same header directly. Display support is disabled; OpenMP is not enabled.
- Build the local bridge with `python scripts/build_vision.py`; output goes to ignored
  `backend/vendor/bin/`. The bridge is specific to the local platform.

## ZXing-C++ 2.3.0

- Source: [official v2.3.0 archive](https://github.com/zxing-cpp/zxing-cpp/archive/refs/tags/v2.3.0.zip).
- Vendored file: `zxing-2.3.0.zip`, upstream source archive.
- SHA-256: `89b70f6175c6347d72bdc72722d643c0f461dc8a0d9bbc4c927a240b32b706f2`.
- License: Apache-2.0; upstream license/notice files are retained in the source archive
  and copied with its full source tree to barcode exports.
- Builder binding: `zxing-cpp==2.3.0` in `requirements.txt`.
- Export builds use C++20 with readers enabled; writers, examples and tests are disabled.
  CMake uses the included source and does not fetch anything from the network.

OpenCV development libraries remain a build prerequisite for exports. Only its core,
imgproc and imgcodecs modules are requested. The builder uses one OpenCV thread with
OpenCL disabled. Dependency licenses remain applicable when distributing generated programs.
