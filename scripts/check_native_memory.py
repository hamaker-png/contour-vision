"""Reproduce the bounded Windows native frame-lifetime memory comparison.

Run from the repository root after scripts/setup_native.py has prepared the local
Windows toolchain::

    python scripts/check_native_memory.py
    python scripts/check_native_memory.py --output artifacts/my-new-memory-run

This compiles two versions of the same fresh 58-operation export. The retaining
control removes only generated frame/batch erase calls. Both receive identical
Windows peak-memory instrumentation. Each child is monitored against 480 MiB and
30 seconds, with concurrent stdout/stderr draining. Results test one fixture;
single-run timings are recorded for context, not evidence of a general speedup.

Each run requires a new output directory, preserving previous benchmark evidence.
"""

from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import zipfile

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import Measurements
from backend.search_execution import execute
from backend.timeline_exporter import TimelineExportRequest, export_timeline
from backend.timelines import Operation, Timeline, execution_plan


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def op(identifier, kind, **params):
    return Operation(id=identifier, kind=kind, params=params)


def branch_operations(prefix):
    return [op(f"{prefix}-inv{i}", "invert") for i in range(4)] + [
        op(prefix + "-gray", "grayscale"), op(prefix + "-mask", "threshold", value=60),
        op(prefix + "-objects", "contours")]


def semantic(value):
    if isinstance(value, dict):
        return {key: semantic(child) for key, child in value.items() if key != "latency_ms"}
    if isinstance(value, list):
        return [semantic(child) for child in value]
    return value


class MemoryCounters(ct.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ct.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
        "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
        "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


INSTRUMENT = r'''#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>
#include <iostream>
struct MemoryPeakReporter {~MemoryPeakReporter(){PROCESS_MEMORY_COUNTERS info{};info.cb=sizeof(info);if(GetProcessMemoryInfo(GetCurrentProcess(),&info,sizeof(info)))std::cerr<<"NATIVE_PEAK_WORKING_SET="<<info.PeakWorkingSetSize<<"\n";}};
'''


def run_variant(name, destination, input_path, env, get_memory):
    binary = destination / "build" / f"{name}.exe"
    output, preview = destination / f"{name}-final.png", destination / f"{name}-preview.png"
    process = subprocess.Popen([str(binary), "--output", str(output), "--preview", str(preview), str(input_path)],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace")
    captured = {}

    def drain():
        try:
            captured["stdout"], captured["stderr"] = process.communicate()
        except Exception as error:
            captured["error"] = error

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    started, observed, violation = time.monotonic(), 0, None
    try:
        while process.poll() is None:
            counters = MemoryCounters()
            counters.cb = ct.sizeof(counters)
            if get_memory(int(process._handle), ct.byref(counters), ct.sizeof(counters)):
                observed = max(observed, counters.PeakWorkingSetSize)
                if counters.WorkingSetSize > 480 * 1048576:
                    violation = f"{name} exceeded 480 MiB safety limit"
                    break
            if time.monotonic() - started > 30:
                violation = f"{name} exceeded 30 second limit"
                break
            time.sleep(.005)
    finally:
        if process.poll() is None:
            process.kill()
        reader.join(2)
    if reader.is_alive():
        raise RuntimeError(f"{name}: output drain did not finish after process termination")
    if "error" in captured:
        raise RuntimeError(f"{name}: output drain failed") from captured["error"]
    stdout, stderr = captured["stdout"], captured["stderr"]
    (destination / f"{name}-stdout.txt").write_text(stdout, encoding="utf-8")
    (destination / f"{name}-stderr.txt").write_text(stderr, encoding="utf-8")
    if violation:
        raise RuntimeError(violation)
    if process.returncode:
        raise RuntimeError(f"{name} exited {process.returncode}: {stderr}")
    peak_match = re.search(r"NATIVE_PEAK_WORKING_SET=(\d+)", stderr)
    if not peak_match:
        raise RuntimeError(f"{name}: native peak-memory instrumentation did not report")
    peak = int(peak_match.group(1))
    assert peak >= observed
    data = json.loads(stdout)
    write_json(destination / f"{name}-output.json", data)
    record = {"variant": name, "peak_working_set_bytes": peak,
              "peak_working_set_MiB": round(peak / 1048576, 2),
              "native_pipeline_ms": data["latency_ms"],
              "wall_ms": round((time.monotonic() - started) * 1000, 2),
              "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    print(json.dumps(record), flush=True)
    final_image = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
    preview_image = cv2.imread(str(preview), cv2.IMREAD_UNCHANGED)
    assert final_image is not None and preview_image is not None
    return record, data, final_image, preview_image


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, help="New output directory; default artifacts/native-memory-replays/<UTC>")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This benchmark uses Windows PeakWorkingSetSize and the project-local Windows toolchain.")
    cmake_binary = ROOT / ".venv/Lib/site-packages/cmake/data/bin/cmake.exe"
    ninja = ROOT / ".venv/Scripts/ninja.exe"
    compiler = ROOT / ".tools/cxx.cmd"
    opencv = ROOT / ".tools/opencv-build"
    for required in (cmake_binary, ninja, compiler, opencv / "OpenCVConfig.cmake"):
        if not required.is_file():
            parser.error(f"Missing local native dependency: {required}. Run scripts/setup_native.py first.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = (args.output or ROOT / "artifacts/native-memory-replays" / stamp).resolve()
    if destination.exists():
        parser.error(f"Output already exists; choose a new directory to preserve earlier evidence: {destination}")
    destination.mkdir(parents=True)
    supports = [f"support{i}" for i in range(7)]
    graphs = [Timeline(id="main", name="Primary with seven confirmations", operations=[
        op("common", "gamma", gamma=1), *branch_operations("main"),
        op("agreement", "confirm", pipeline_ids=",".join(supports), min_support=7)])]
    graphs += [Timeline(id=name, name=name, parent_id="main", fork_after="common",
                        operations=branch_operations(name)) for name in supports]
    measurements = Measurements(fields=["length", "width", "area", "center", "color"])
    configuration = TimelineExportRequest(timelines=graphs, selected_timeline_id="main", measurements=measurements)
    order = execution_plan(graphs, "main")[0]
    assert len(order) == 58
    package = export_timeline(configuration)
    (destination / "download.zip").write_bytes(package)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        source = archive.read("detector.cpp").decode("utf-8")
    erase = re.compile(r'(?:frames|batches)\.erase\("[A-Za-z0-9_-]+"\);')
    retaining, removed = erase.subn("", source)
    assert removed >= 50, "Expected generated frame/batch lifetime erasures were not found"
    main_pattern = re.compile(r"int\s+main\s*\(int\s+argc\s*,\s*char\s*\*\s*\*\s*argv\s*\)\s*\{")
    for name, text in [("released", source), ("retaining", retaining)]:
        instrumented, replacements = main_pattern.subn(lambda match: match.group(0) + "MemoryPeakReporter memory_peak_reporter;", text)
        assert replacements == 1, "Expected exactly one generated main function"
        (destination / f"{name}.cpp").write_text(INSTRUMENT + instrumented, encoding="utf-8")
    cmake = ["cmake_minimum_required(VERSION 3.16)", "project(native_memory LANGUAGES CXX)",
             "find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)"]
    for name in ("released", "retaining"):
        cmake += [f"add_executable({name} {name}.cpp)", f"target_compile_features({name} PRIVATE cxx_std_17)",
                  f"target_include_directories({name} PRIVATE ${{OpenCV_INCLUDE_DIRS}})",
                  f"target_link_libraries({name} PRIVATE ${{OpenCV_LIBS}} psapi)"]
    (destination / "CMakeLists.txt").write_text("\n".join(cmake) + "\n", encoding="utf-8")
    write_json(destination / "graph.json", configuration.model_dump())
    image = np.zeros((1536, 1536, 3), np.uint8)
    cv2.rectangle(image, (150, 170), (470, 610), (35, 150, 240), cv2.FILLED)
    cv2.circle(image, (1010, 460), 210, (220, 180, 40), cv2.FILLED)
    cv2.rectangle(image, (540, 920), (1090, 1250), (160, 200, 90), cv2.FILLED)
    input_path = destination / "input.png"
    assert cv2.imwrite(str(input_path), image)
    env = {**os.environ, "ZIG_GLOBAL_CACHE_DIR": str(ROOT / ".tools/zig-cache"),
           "ZIG_LOCAL_CACHE_DIR": str(ROOT / ".tools/zig-local-cache"), "PYTHONDONTWRITEBYTECODE": "1"}
    build = destination / "build"
    configure = [str(cmake_binary), "-S", str(destination), "-B", str(build), "-G", "Ninja",
                 "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_MAKE_PROGRAM={ninja.as_posix()}",
                 f"-DCMAKE_CXX_COMPILER={compiler.as_posix()}", f"-DOpenCV_DIR={opencv.as_posix()}"]
    for label, command in [("configure", configure), ("build", [str(cmake_binary), "--build", str(build), "--parallel", "2"])]:
        result = subprocess.run(command, env=env, text=True, encoding="utf-8", errors="replace",
                                capture_output=True, timeout=120)
        (destination / f"{label}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{label} failed; see {destination / (label + '.log')}")
    print(f"Both instrumented actual exports compiled: {destination}", flush=True)
    get_memory = ct.WinDLL("psapi").GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ct.POINTER(MemoryCounters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    runs = [run_variant(name, destination, input_path, env, get_memory) for name in ("released", "retaining")]
    assert semantic(runs[0][1]) == semantic(runs[1][1])
    assert np.array_equal(runs[0][2], runs[1][2]) and np.array_equal(runs[0][3], runs[1][3])
    assert [row["id"] for row in runs[0][1]["operations"]] == [operation.id for operation in order]
    assert len(runs[0][1]["measurement_steps"]) == 9
    assert all(row["count"] == 3 for row in runs[0][1]["measurement_steps"])
    assert all(d["measurements"]["supporting_branches"] == 7 for d in runs[0][1]["measurement_steps"][-1]["detections"])
    expected, _ = execute(image, graphs, "main", measurements)
    assert np.array_equal(expected.image, runs[0][2]) and expected.details["count"] == 3
    report = {"recorded_utc": datetime.now(timezone.utc).isoformat(), "report_directory": str(destination),
              "input_pixels": int(image.shape[0] * image.shape[1]), "operations": len(order),
              "pipelines": len(graphs), "support_branches": 7, "control_removed_erase_calls": removed,
              "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
              "runs": [entry[0] for entry in runs],
              "peak_reduction_percent": round(100 * (1 - runs[0][0]["peak_working_set_bytes"] / runs[1][0]["peak_working_set_bytes"]), 2),
              "identical_semantic_json": True, "identical_final_pixels": True,
              "identical_preview_pixels": True, "matches_python_final_pixels": True,
              "measurement_steps": 9, "final_objects": 3,
              "safety_limits": {"child_timeout_seconds": 30, "working_set_MiB": 480},
              "method": "Windows GetProcessMemoryInfo PeakWorkingSetSize, reported by identical RAII instrumentation in both actual export variants; only generated lifetime erase calls differ.",
              "limitations": "One 58-operation shared-confirmation fixture. Single-run timing is not a throughput benchmark or evidence of a general speedup."}
    write_json(destination / "results.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
