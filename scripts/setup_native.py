"""Optional, project-local minimal OpenCV build for checking C++ exports on Windows.

Requires pip install ziglang cmake ninja. Uses only project .tools and .venv.
"""
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
TOOLS.mkdir(exist_ok=True)
SITE = ROOT / ".venv/Lib/site-packages"
ZIG = SITE / "ziglang/zig.exe"
CMAKE = SITE / "cmake/data/bin/cmake.exe"
NINJA = ROOT / ".venv/Scripts/ninja.exe"
archive = TOOLS / "opencv-4.12.0.zip"
if not archive.exists():
    print("Downloading OpenCV 4.12.0 source from its official GitHub repository", flush=True)
    urllib.request.urlretrieve("https://codeload.github.com/opencv/opencv/zip/refs/tags/4.12.0", archive)
source = TOOLS / "opencv-4.12.0"
if not source.exists():
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():
            if not (TOOLS / member).resolve().is_relative_to(TOOLS.resolve()):
                raise ValueError("Unsafe archive path")
        z.extractall(TOOLS)
for name, mode in [("cc", "cc"), ("cxx", "c++"), ("ar", "ar"), ("ranlib", "ranlib")]:
    (TOOLS / f"{name}.cmd").write_text(f'@echo off\n"{ZIG}" {mode} %*\n')
env = os.environ.copy()
env["ZIG_GLOBAL_CACHE_DIR"] = str(TOOLS / "zig-cache")
env["ZIG_LOCAL_CACHE_DIR"] = str(TOOLS / "zig-local-cache")
env["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + env["PATH"]
build = TOOLS / "opencv-build"
# CMake persists compiler tool discovery separately from CMakeCache.txt. Repair an
# earlier interrupted configure that ran before these wrapper tools were available.
if (build / "CMakeFiles").exists():
    for file in (build / "CMakeFiles").glob("*/*Compiler.cmake"):
        content = file.read_text()
        content = content.replace('set(CMAKE_AR "CMAKE_AR-NOTFOUND")', f'set(CMAKE_AR "{(TOOLS/"ar.cmd").as_posix()}")')
        content = content.replace('set(CMAKE_RANLIB "CMAKE_RANLIB-NOTFOUND")', f'set(CMAKE_RANLIB "{(TOOLS/"ranlib.cmd").as_posix()}")')
        file.write_text(content)
args = [str(CMAKE), "-S", str(source), "-B", str(build), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        f"-DCMAKE_MAKE_PROGRAM={NINJA.as_posix()}",
        f"-DCMAKE_C_COMPILER={(TOOLS/'cc.cmd').as_posix()}", f"-DCMAKE_CXX_COMPILER={(TOOLS/'cxx.cmd').as_posix()}",
        f"-DCMAKE_AR={(TOOLS/'ar.cmd').as_posix()}", f"-DCMAKE_RANLIB={(TOOLS/'ranlib.cmd').as_posix()}",
        "-DBUILD_LIST=core,imgproc,imgcodecs", "-DBUILD_SHARED_LIBS=OFF", "-DBUILD_TESTS=OFF", "-DBUILD_PERF_TESTS=OFF",
        "-DBUILD_EXAMPLES=OFF", "-DBUILD_opencv_apps=OFF", "-DBUILD_opencv_python3=OFF", "-DBUILD_JAVA=OFF",
        "-DWITH_IPP=OFF", "-DWITH_OPENCL=OFF", "-DWITH_ITT=OFF", "-DWITH_TBB=OFF", "-DWITH_OPENMP=OFF",
        "-DWITH_FFMPEG=OFF", "-DWITH_GSTREAMER=OFF", "-DWITH_MSMF=OFF", "-DWITH_DSHOW=OFF",
        "-DWITH_TIFF=OFF", "-DWITH_OPENEXR=OFF", "-DWITH_JASPER=OFF", "-DWITH_OPENJPEG=OFF", "-DWITH_AVIF=OFF",
        "-DWITH_WEBP=ON", "-DBUILD_WEBP=ON", "-DBUILD_PNG=ON", "-DBUILD_JPEG=ON", "-DBUILD_ZLIB=ON",
        "-DCPU_BASELINE=SSE2", "-DCPU_DISPATCH=", "-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG", "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG"]
subprocess.run(args, env=env, check=True)
subprocess.run([str(CMAKE),"--build",str(build),"--parallel","2"], env=env, check=True)
print("Native OpenCV ready at", build, flush=True)
