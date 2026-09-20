import io
import json
import zipfile
from pathlib import Path

from .models import ExportRequest


def cpp_string(text):
    # JSON string quoting is compatible with these constrained ASCII C++ fields.
    return json.dumps(text, ensure_ascii=True)


def export_cpp(request: ExportRequest) -> bytes:
    s = request.strategy
    m = request.measurements
    constants = []
    for key, value in s.model_dump().items():
        if key in ("name", "rationale"):
            continue
        kind = "bool" if isinstance(value, bool) else "int" if isinstance(value, int) else "double" if isinstance(value, float) else "const char*"
        literal = str(value).lower() if isinstance(value, bool) else cpp_string(value) if isinstance(value, str) else str(value)
        constants.append(f"constexpr {kind} {key} = {literal};")
    constants += [f"constexpr double pixels_per_unit = {m.pixels_per_unit};",
                  f"constexpr const char* unit = {cpp_string(m.unit if m.pixels_per_unit else 'px')};"]
    for field in ["length", "width", "area", "angle", "color", "center"]:
        constants.append(f"constexpr bool measure_{field} = {str(field in m.fields).lower()};")
    source = (Path(__file__).parent / "detector.cpp.in").read_text(encoding="utf-8")
    source = source.replace("// GENERATED_CONSTANTS", "\n".join(constants))
    readme = """# Generated CPU detector

This C++17 program uses only OpenCV core, imgproc, and imgcodecs. It makes no network
requests, uses one CPU thread, and disables OpenCL. No Python, API key, model weights,
GPU runtime, or JSON library is required. OpenCV itself must be installed.

Build with a C++17 compiler, CMake >=3.16, and the OpenCV development package:

    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release

If CMake cannot find OpenCV, add -DOpenCV_DIR=/path/to/opencv/lib/cmake/opencv4
(on Windows, point to the folder containing OpenCVConfig.cmake and put the matching
OpenCV DLL directory on PATH). On Debian/Ubuntu: apt install g++ cmake libopencv-dev.
On macOS: brew install cmake opencv. Windows can use vcpkg install opencv4, with the
vcpkg CMake toolchain, or the official OpenCV Windows SDK plus Visual Studio.

Run (Windows multi-config builds use build/Release/detector.exe):

    ./build/detector image.png
    ./build/detector --output annotated.png image.png
    ./build/detector image1.png image2.jpg

One JSON object per input image is written to stdout. Failed images are reported
to stderr and cause a nonzero exit code. --output supports one image only.
All filenames and control characters are JSON-escaped. Transparent images are
composited onto white. Use ordinary 8-bit PNG, JPEG, or WebP inputs.

The processing size is capped at 1280px on the longest side, matching the builder.
Bounding boxes and centers are reported in ORIGINAL image pixels. Length and width
are the long/short sides of a rotated minimum-area rectangle. Angle is that rectangle's
long axis in image coordinates, clockwise modulo 180 degrees; nearly square/circular
objects have no stable axis: angle is null when rectangle aspect ratio is <=1.05.
Area is external contour area: holes are not subtracted.
Mean RGB averages the filled external contour and may include holes/background.
Length/width/area use configured physical units only if pixels_per_unit is positive.
Area is in squared units. Calibration requires the same resolution, camera distance,
and object plane. Perspective distortion and occlusion invalidate simple calibration.

Preview timing is measured in the Python builder; benchmark this binary on the target
CPU for deployment timing. Small-sample scores do not establish field reliability.
Test independent images with lighting changes, confusers, and absent targets.

Edit config.json for reference; this binary embeds constants in detector.cpp. Changing
config.json alone does not reconfigure the compiled program. Re-export or edit the
constants in detector.cpp and rebuild.
"""
    cmake = """cmake_minimum_required(VERSION 3.16)
project(cpu_detector LANGUAGES CXX)
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)
add_executable(detector detector.cpp)
target_compile_features(detector PRIVATE cxx_std_17)
target_include_directories(detector PRIVATE ${OpenCV_INCLUDE_DIRS})
target_link_libraries(detector PRIVATE ${OpenCV_LIBS})
if(MSVC)
  target_compile_options(detector PRIVATE /O2 /W4)
else()
  target_compile_options(detector PRIVATE -O3 -Wall -Wextra)
endif()
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in {"detector.cpp": source, "CMakeLists.txt": cmake, "README.md": readme,
                              "config.json": json.dumps(request.model_dump(), indent=2)}.items():
            archive.writestr(name, content)
    return buffer.getvalue()
