"""Exercise native image loading with small, reproducible EXIF and dimension fixtures.

Run from the repository root using the project's Python environment::

    python scripts/check_native_loader_bounds.py
    python scripts/check_native_loader_bounds.py --binary path/to/detector.exe

The supplied binary must be an export of grayscale -> gamma(0.7), matching the
default artifacts/expanded-native/gamma/build/detector.exe fixture. This script
does not compile anything or call an AI provider. Each process has a three-second
timeout and, on Windows, a 200 MiB monitored working-set limit. All image fixtures
are small; oversized inputs contain headers only, not compressed giant bitmaps.

Every run gets a new report directory. Malformed TIFF interpretation differences
are recorded separately from assertions on valid images and container boundaries.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import warnings
import zlib

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import decode_image
from backend.models import Measurements
from backend.timelines import Frame, Operation, apply_operation


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def png_chunk(name, payload):
    return (struct.pack(">I", len(payload)) + name + payload
            + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF))


def webp_chunk(name, payload):
    return name + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) % 2 else b"")


def webp_container(chunks):
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WEBP" + chunks


def tiff(orientation=6, endian="<", kind=3, count=1):
    value = (struct.pack(endian + "H", orientation) + b"\0\0" if kind == 3
             else struct.pack(endian + "I", orientation))
    return ((b"II" if endian == "<" else b"MM") + struct.pack(endian + "HIH", 42, 8, 1)
            + struct.pack(endian + "HHI", 0x112, kind, count) + value + b"\0" * 4)


def image_bases():
    gray = np.zeros((40, 64), np.uint8)
    gray[3:12, 7:35] = 190
    gray[23:37, 42:61] = 80
    gray[14:20, 25:30] = 255
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    rgba = np.concatenate([rgb, np.full(gray.shape + (1,), 255, np.uint8)], axis=2)
    rgba[:20, :, 3] = 73

    def save(fmt, pixels, exif=None):
        output = io.BytesIO()
        options = {"format": fmt}
        if fmt == "JPEG":
            options.update(quality=100, subsampling=0)
        if fmt == "WEBP":
            options["lossless"] = True
        if exif is not None:
            options["exif"] = exif
        Image.fromarray(pixels).save(output, **options)
        return output.getvalue()

    exif = Image.Exif()
    exif[274] = 1
    return ({"png": save("PNG", rgba), "jpeg": save("JPEG", rgb),
             "webp": save("WEBP", rgba, exif)}, save("PNG", rgb), save("WEBP", rgb))


def inject(fmt, data, payload, trailing=False):
    if fmt == "png":
        chunk = png_chunk(b"eXIf", payload)
        return data + chunk if trailing else data[:33] + chunk + data[33:]
    if fmt == "jpeg":
        payload = b"Exif\0\0" + payload
        return data[:2] + b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + data[2:]
    chunk = webp_chunk(b"EXIF", payload)
    if trailing:
        return data + chunk
    chunks, p = [], 12
    while p + 8 <= len(data):
        size = struct.unpack_from("<I", data, p + 4)[0]
        end = p + 8 + size + (size & 1)
        if data[p:p + 4] != b"EXIF":
            chunks.append(data[p:end])
        p = end
    return webp_container(b"".join(chunks) + chunk)


def metadata_cases(bases, plain_png, plain_webp):
    cases = []
    for fmt, data in bases.items():
        for endian in ("<", ">"):
            for orientation in range(1, 9):
                cases.append((f"valid-{fmt}-{endian == '>'}-{orientation}", fmt,
                              inject(fmt, data, tiff(orientation, endian))))
    valid = tiff()
    payloads = {f"trunc-{n}": valid[:n] for n in range(len(valid))}
    payloads.update({"bad-endian": b"ZZ" + valid[2:], "bad-magic": valid[:2] + b"\0\0" + valid[4:],
                     "offset-max": valid[:4] + b"\xff" * 4 + valid[8:],
                     "count-max": valid[:8] + b"\xff\xff" + valid[10:],
                     "orientation-zero": tiff(0), "orientation-nine": tiff(9),
                     "wrong-type-long": tiff(kind=4), "wrong-count-two": tiff(count=2)})
    for fmt, data in bases.items():
        for name, payload in payloads.items():
            cases.append((f"{fmt}-{name}", fmt, inject(fmt, data, payload)))
    cases.extend([("png-after-iend", "png", inject("png", plain_png, valid, True)),
                  ("webp-after-riff", "webp", inject("webp", plain_webp, valid, True))])
    for fmt, data in bases.items():
        for n in (0, 1, 2, 3, 7, 8, 11, 12, 15, 20, len(data) // 2):
            cases.append((f"{fmt}-container-trunc-{n}", fmt, data[:n]))
    return cases


def dimension_cases(valid_webp):
    def png(w, h):
        return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + png_chunk(b"IEND", b""))

    def jpeg(w, h):
        return b"\xff\xd8\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00\xff\xd9"

    def vp8x(w, h):
        return webp_container(webp_chunk(b"VP8X", b"\0" * 4 + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little")))

    def vp8l(w, h):
        return webp_container(webp_chunk(b"VP8L", b"\x2f" + struct.pack("<I", (w - 1) | ((h - 1) << 14))))

    def vp8(w, h):
        return webp_container(webp_chunk(b"VP8 ", b"\0" * 3 + b"\x9d\x01\x2a" + struct.pack("<HH", w, h)))

    cases = []
    for name, create, maximum in [("png", png, 0xFFFFFFFF), ("jpeg", jpeg, 65535),
                                   ("vp8x", vp8x, 1 << 24), ("vp8l", vp8l, 16384), ("vp8", vp8, 16383)]:
        for label, w, h in [("limit-plus", 6001, 4000), ("maximum", maximum, maximum), ("wide", maximum, 2)]:
            expected = "Input exceeds 24 megapixels" if w * h > 24000000 else None
            cases.append((f"{name}-{label}", create(w, h), expected))
        if name in ("png", "jpeg", "vp8"):
            for w, h in [(0, 40), (40, 0), (0, 0)]:
                cases.append((f"{name}-zero-{w}-{h}", create(w, h), "Invalid input dimensions"))
        data = create(6001, 4000)
        cases.extend((f"{name}-trunc-{n}", data[:n], None) for n in range(len(data)))
    for offset in (4, 16):
        for value in (0, 1, 0xFFFFFFFF):
            data = bytearray(valid_webp)
            data[offset:offset + 4] = struct.pack("<I", value)
            cases.append((f"webp-length-{offset}-{value}", bytes(data), None))
    return cases


class WindowsMemory:
    def __init__(self):
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        self.counters = Counters
        self.get = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        self.get.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        self.get.restype = wintypes.BOOL

    def read(self, process):
        info = self.counters()
        info.cb = ctypes.sizeof(info)
        if self.get(int(process._handle), ctypes.byref(info), ctypes.sizeof(info)):
            return info.PeakWorkingSetSize, info.WorkingSetSize
        return 0, 0


def run_native(binary, path, output, memory):
    command = [str(binary)]
    if output:
        command.extend(["--output", str(output)])
    command.append(str(path))
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    peak, violation = 0, None
    while process.poll() is None:
        if memory:
            recorded, current = memory.read(process)
            peak = max(peak, recorded)
            if current > 200 * 1048576:
                violation = "memory limit"
                process.kill()
        if time.monotonic() - started > 3:
            violation = "timeout"
            process.kill()
        time.sleep(.001)
    if memory:
        peak = max(peak, memory.read(process)[0])
    _, stderr = process.communicate(timeout=1)
    return {"returncode": process.returncode, "stderr": stderr.decode("utf-8", errors="replace")[-300:],
            "wall_ms": round((time.monotonic() - started) * 1000, 2),
            "peak_MiB": round(peak / 1048576, 2) if memory else None, "violation": violation}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--binary", type=Path, default=ROOT / "artifacts/expanded-native/gamma/build/detector.exe")
    parser.add_argument("--output", type=Path, help="New, nonexisting report directory; defaults to a timestamped artifacts directory")
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        parser.error(f"Native gamma fixture not found: {binary}. Supply a grayscale -> gamma(0.7) export with --binary.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = (args.output or ROOT / "artifacts/native-loader-bounds" / stamp).resolve()
    if destination.exists():
        parser.error(f"Output already exists; choose a new path to preserve earlier evidence: {destination}")
    destination.mkdir(parents=True)
    memory = WindowsMemory() if os.name == "nt" else None
    bases, plain_png, plain_webp = image_bases()
    metadata, dimensions = [], []
    for name, fmt, data in metadata_cases(bases, plain_png, plain_webp):
        path, output = destination / f"{name}.{fmt}", destination / f"{name}-out.png"
        path.write_bytes(data)
        expected = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                source = decode_image(f"data:image/{fmt};base64," + base64.b64encode(data).decode("ascii"))
            frame = Frame(source, "color")
            for operation in [Operation(id="gray", kind="grayscale"), Operation(id="gamma", kind="gamma", params={"gamma": .7})]:
                frame = apply_operation(frame, operation, source, Measurements(fields=[]))
            expected = frame.image
            python = {"status": "ok", "shape": list(expected.shape)}
        except Exception as error:
            python = {"status": "error", "type": type(error).__name__, "message": str(error)[:180]}
        native = run_native(binary, path, output, memory)
        if native["returncode"] == 0:
            result = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
            native["shape"] = list(result.shape) if result is not None else None
            match = expected is not None and result is not None and np.array_equal(result, expected)
        else:
            match = expected is None
        metadata.append({"case": name, "python": python, "native": native, "match": match})
    for name, data, expected_error in dimension_cases(bases["webp"]):
        path = destination / f"dimensions-{name}.bin"
        path.write_bytes(data)
        dimensions.append({"case": name, "bytes": len(data), "expected_error": expected_error,
                           "native": run_native(binary, path, None, memory)})
    runs = [record["native"] for record in metadata + dimensions]
    failures = {
        "valid_parity": [r for r in metadata if r["case"].startswith("valid-") and not r["match"]],
        "container_boundaries": [r for r in metadata if r["case"] in ("png-after-iend", "webp-after-riff") and not r["match"]],
        "unexpected_python_errors": [r for r in metadata if r["python"]["status"] == "error" and r["python"]["type"] != "ValueError"],
        "native_errors": [r for r in metadata + dimensions if r["native"]["violation"] or r["native"]["returncode"] not in (0, 1)],
        "dimension_errors": [r for r in dimensions if r["expected_error"] and (r["native"]["returncode"] != 1 or r["expected_error"] not in r["native"]["stderr"])],
    }
    summary = {"binary": str(binary), "report_directory": str(destination),
               "expected_pipeline": ["grayscale", "gamma(0.7)"], "metadata_cases": len(metadata),
               "valid_orientation_cases": sum(r["case"].startswith("valid-") for r in metadata),
               "dimension_cases": len(dimensions), "max_dimension_fixture_bytes": max(r["bytes"] for r in dimensions),
               "max_wall_ms": max(r["wall_ms"] for r in runs),
               "max_peak_MiB": max(r["peak_MiB"] for r in runs) if memory else None,
               "memory_method": "Windows GetProcessMemoryInfo PeakWorkingSetSize" if memory else "Not measured on this platform; three-second subprocess timeout enforced",
               "malformed_interpretation_differences": sum(not r["match"] for r in metadata if not r["case"].startswith("valid-") and r["case"] not in ("png-after-iend", "webp-after-riff")),
               "failure_counts": {name: len(items) for name, items in failures.items()},
               "passed": not any(failures.values())}
    write_json(destination / "report.json", {"summary": summary, "failures": failures, "metadata": metadata, "dimensions": dimensions})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
