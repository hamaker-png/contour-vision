"""Reproducible labeled internet-image benchmark and sample C++ exports."""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engine import run_experiment
from backend.exporter import export_cpp
from backend.models import ExportRequest, Measurements, Sample, Strategy

root = Path(__file__).resolve().parents[1]
out = root / "artifacts"
out.mkdir(exist_ok=True)
manifest = json.loads((root / "examples/manifest.json").read_text())
report = []
for example in manifest:
    image = (root / "examples" / example["filename"]).read_bytes()
    sample = Sample(id=example["id"], name=example["filename"], data="data:image/png;base64,"+base64.b64encode(image).decode(),
                    labeled=True, boxes=example["boxes"])
    measures = Measurements(fields=["length","width","area","angle","color","center"])
    experiment = run_experiment([sample], [Strategy(**s) for s in example["strategies"]], measures)
    best = experiment["strategies"][0]
    for key, value in best["results"][0]["stages"].items():
        (out / f"{example['id']}-{key}.png").write_bytes(base64.b64decode(value.split(",")[1]))
    (out / f"{example['id']}-detector.zip").write_bytes(export_cpp(ExportRequest(strategy=Strategy(**best["strategy"]), measurements=measures, description=example["description"])))
    rows = [{"name": c["strategy"]["name"], "count": c["results"][0]["count"], "metrics": c["train"], "latency_ms": c["latency_ms"]} for c in experiment["strategies"]]
    report.append({"example": example["id"], "source": example["source"], "strategies": rows})
    print(json.dumps(report[-1], indent=2))
(out / "benchmark.json").write_text(json.dumps(report, indent=2))
