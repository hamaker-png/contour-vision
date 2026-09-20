"""Fixed-configuration robustness evidence. Never tunes against these variants."""
import argparse
import base64
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import data_url
from backend.models import Sample, Strategy
from backend.timelines import TimelineRunRequest, run_timelines, timelines_from_strategies


def cases(example):
    im = cv2.imread(str(ROOT / "examples" / example["filename"]), cv2.IMREAD_UNCHANGED)
    if im.ndim == 2: im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    if im.shape[2] == 4:
        alpha = im[:,:,3:4].astype(float)/255
        im = np.round(im[:,:,:3]*alpha + 255*(1-alpha)).astype(np.uint8)
    boxes = example["boxes"]
    rng = np.random.default_rng(741)
    yield "original", "original fit", im, boxes
    for name, variant in [
        ("dim_65pct", np.round(im*.65).astype(np.uint8)),
        ("bright_125pct", np.clip(im*1.25,0,255).astype(np.uint8)),
        ("blur_5px", cv2.GaussianBlur(im,(5,5),1.3)),
        ("noise_sigma8", np.clip(im.astype(float)+rng.normal(0,8,im.shape),0,255).astype(np.uint8)),
        ("half_resolution", cv2.resize(im,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)),
    ]: yield name, "derived robustness", variant, boxes
    rotated = cv2.rotate(im,cv2.ROTATE_90_CLOCKWISE)
    rotated_boxes = [{"x":1-b["y"]-b["height"], "y":b["x"], "width":b["height"], "height":b["width"]} for b in boxes]
    yield "rotate_90deg", "derived robustness", rotated, rotated_boxes
    yield "empty_white", "synthetic negative", np.full_like(im,255), []
    yield "empty_gray", "synthetic negative", np.full_like(im,125), []
    noise = np.clip(125+rng.normal(0,6,im.shape),0,255).astype(np.uint8)
    yield "textured_negative", "synthetic negative", noise, []


def benchmark(extra=False, hard=False):
    manifest = json.loads((ROOT / "examples/manifest.json").read_text())
    if extra:manifest += json.loads((ROOT / "examples/additional-fixtures.json").read_text())
    records=[]
    for example in manifest:
        timelines=timelines_from_strategies([Strategy.model_validate(s) for s in example["strategies"]])
        winner=2 if example["id"]=="coins" else 0
        # All alternatives run, but the predeclared candidate is used for robustness scoring.
        variants=list(cases(example))
        if hard and example['id']=='red-candies':
            image=cv2.imread(str(ROOT/'examples'/example['filename']))
            # This same-color distractor is outside every original manually labeled target.
            distractor=image.copy();cv2.circle(distractor,(115,50),27,(0,0,230),-1)
            variants.append(('red_round_distractor','declared challenge',distractor,example['boxes']))
            occluded=image.copy();cv2.rectangle(occluded,(250,187),(302,225),(255,255,255),-1)
            variants.append(('partial_occlusion','declared challenge',occluded,example['boxes']))
            desaturated=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);desaturated=cv2.cvtColor(desaturated,cv2.COLOR_GRAY2BGR)
            variants.append(('color_information_lost','declared challenge',desaturated,example['boxes']))
        for name, group, image, boxes in variants:
            encoded=data_url(image);encoding='PNG'
            if len(encoded)>10_000_000:
                _,buffer=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,95]);encoded='data:image/jpeg;base64,'+base64.b64encode(buffer).decode();encoding='JPEG quality 95 (large image)'
            sample=Sample(id=example["id"]+"-"+name,name=name,data=encoded,labeled=True,boxes=boxes,split="validation" if name!="original" else "train")
            start=time.perf_counter()
            result=run_timelines(TimelineRunRequest(samples=[sample],timelines=timelines))["images"][0]
            wall=(time.perf_counter()-start)*1000
            stage=result["stages"][timelines[winner].operations[-1].id]
            record={"source":example["id"],"case":name,"group":group,"encoding":encoding,"candidate":timelines[winner].name,
                    "fit":stage["details"]["fit"],"expected":len(boxes),"detected":stage["details"]["count"],
                    "path_ms":result["timelines"][winner]["local_ms"],"all_paths_wall_ms":wall}
            records.append(record)
    aggregates={}
    for group in sorted({r["group"] for r in records}):
        rows=[r for r in records if r["group"]==group]
        tp=sum(r["fit"]["tp"] for r in rows); fp=sum(r["fit"]["fp"] for r in rows); fn=sum(r["fit"]["fn"] for r in rows)
        aggregates[group]={"images":len(rows),"tp":tp,"fp":fp,"fn":fn,"f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                           "exact_count_images":sum(r["expected"]==r["detected"] for r in rows)}
    return {"method":f"Fixed predeclared presets across {len(manifest)} original scenes, one configured task per scene. Derived variants are not independent generalization. No tuning.",
            "groups":aggregates,"median_all_paths_wall_ms":float(np.median([r["all_paths_wall_ms"] for r in records])),
            "records":records}


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",default="artifacts/validation/baseline-benchmark.json");parser.add_argument('--extra',action='store_true');parser.add_argument('--hard',action='store_true');args=parser.parse_args()
    report=benchmark(args.extra,args.hard);destination=ROOT/args.output;destination.parent.mkdir(exist_ok=True,parents=True)
    destination.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"groups":report["groups"],"median_all_paths_wall_ms":report["median_all_paths_wall_ms"]},indent=2))
