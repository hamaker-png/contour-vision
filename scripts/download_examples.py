"""Fetch small public CV fixtures from their upstream sources. Never downloads code."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "examples"
DEST.mkdir(exist_ok=True)
filename = "Green_shapes.png"
digest = hashlib.md5(filename.encode()).hexdigest()
FILES = {
    "green-shapes.png": f"https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{filename}",
    "smarties.png": "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/smarties.png",
    "coins.png": "https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/coins.png",
}
for name, url in FILES.items():
    path = DEST / name
    if not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "Contour-CV-Workbench/1.0 (educational test fixtures)"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read(8_000_001)
            if len(raw) > 8_000_000 or not raw.startswith(b"\x89PNG"):
                raise ValueError("Expected a small PNG")
            path.write_bytes(raw)
        except Exception as exc:
            print(f"{name}: {exc}")
            continue
    print(f"{name}: {path.stat().st_size} bytes; sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
