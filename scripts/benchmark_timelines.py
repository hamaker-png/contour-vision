"""Reproduce the editable-graph experiments and save all intermediate previews."""
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import Measurements, Sample, Strategy
from backend.timelines import TimelineRunRequest, run_timelines, timelines_from_strategies

destination = ROOT / "artifacts" / "timelines"
destination.mkdir(parents=True, exist_ok=True)
records = []
for example in json.loads((ROOT / "examples" / "manifest.json").read_text()):
    sample = Sample(id=example["id"], name=example["filename"], boxes=example["boxes"], labeled=True,
                    data="data:image/png;base64," + base64.b64encode((ROOT / "examples" / example["filename"]).read_bytes()).decode())
    timelines = timelines_from_strategies([Strategy.model_validate(s) for s in example["strategies"]])
    request = TimelineRunRequest(samples=[sample], timelines=timelines,
                                 measurements=Measurements(fields=["length", "width", "area", "color", "center", "angle"]))
    result = run_timelines(request)
    directory = destination / example["id"]
    directory.mkdir(exist_ok=True)
    for stage in result["images"][0]["stages"].values():
        preview = stage.pop("image", None)
        if preview:
            filename = stage["id"] + ".png"
            (directory / filename).write_bytes(base64.b64decode(preview.split(",", 1)[1]))
            stage["preview_file"] = filename
    (directory / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for timeline, summary in zip(timelines, result["images"][0]["timelines"]):
        stage = result["images"][0]["stages"][timeline.operations[-1].id]
        record = {"example": example["id"], "timeline": timeline.name, "count": stage["details"]["count"],
                  "fit": stage["details"].get("fit"), "local_ms": summary["local_ms"], "errors": summary["errors"]}
        records.append(record)
        print(f"{example['id']}: {timeline.name}: {record['count']} objects, F1={record['fit']['f1']:.3f}, {record['local_ms']:.3f} ms")
(destination / "summary.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
