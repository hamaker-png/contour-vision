"""Editable, typed transform graphs. A branch inherits a live prefix by stable node ID."""
from __future__ import annotations

import os
import platform
import statistics
import time
from dataclasses import dataclass, field
from typing import Literal

import cv2
import numpy as np
from pydantic import Field, model_validator

from .engine import contrast, counts, data_url, decode_image
from .models import AnalyzeRequest, Measurements, Sample, Strategy, StrictModel
from .cpu_work import check_cancelled
from .vision_params import EXTRA_CATALOG, DETECTORS, LIBRARIES, supporting_ids


class KernelParams(StrictModel):
    kernel: int = Field(default=3, ge=1, le=31)

    @model_validator(mode="after")
    def odd(self):
        if self.kernel % 2 == 0:
            raise ValueError("Kernel size must be odd")
        return self


class NoParams(StrictModel):
    pass


class ResizeParams(StrictModel):
    max_side: int = Field(default=1280, ge=64, le=2048)


class HSVParams(StrictModel):
    hue_low: int = Field(default=170, ge=0, le=179)
    hue_high: int = Field(default=10, ge=0, le=179)
    saturation_low: int = Field(default=80, ge=0, le=255)
    saturation_high: int = Field(default=255, ge=0, le=255)
    value_low: int = Field(default=40, ge=0, le=255)
    value_high: int = Field(default=255, ge=0, le=255)

    @model_validator(mode="after")
    def ranges(self):
        if self.saturation_low > self.saturation_high or self.value_low > self.value_high:
            raise ValueError("Saturation/value lower bounds must not exceed upper bounds")
        return self


class ThresholdParams(StrictModel):
    value: int = Field(default=127, ge=0, le=255)


class AdaptiveParams(StrictModel):
    block_size: int = Field(default=31, ge=3, le=101)
    constant: float = Field(default=5, ge=-40, le=40)

    @model_validator(mode="after")
    def odd(self):
        if self.block_size % 2 == 0:
            raise ValueError("Block size must be odd")
        return self


class CannyParams(StrictModel):
    low: int = Field(default=50, ge=0, le=254)
    high: int = Field(default=150, ge=1, le=255)

    @model_validator(mode="after")
    def ordered(self):
        if self.low >= self.high:
            raise ValueError("Canny low must be less than high")
        return self


class ChannelParams(StrictModel):
    channel: Literal["red", "green", "blue", "hue", "saturation", "value"] = "saturation"


class ClaheParams(StrictModel):
    clip_limit: float = Field(default=2, ge=.1, le=10)
    tile_size: int = Field(default=8, ge=2, le=32)


class ContourParams(StrictModel):
    min_area: float = Field(default=.001, ge=.00001, le=.9)
    max_area: float = Field(default=.85, gt=0, le=1)
    min_circularity: float = Field(default=0, ge=0, le=1)
    min_solidity: float = Field(default=0, ge=0, le=1)
    min_aspect: float = Field(default=1, ge=1, le=100)
    max_aspect: float = Field(default=100, ge=1, le=100)
    reject_border: bool = True

    @model_validator(mode="after")
    def ordered(self):
        if self.min_area > self.max_area or self.min_aspect > self.max_aspect:
            raise ValueError("Lower bounds must not exceed upper bounds")
        return self


# name, accepted image types, help text, parameter schema
CATALOG = {
    "resize": ("Resize", ["color", "gray", "mask"], "Reduce pixel count while preserving aspect ratio. Never enlarges an image.", ResizeParams),
    "gaussian_blur": ("Gaussian blur", ["color", "gray", "mask"], "Smooth noise. Blurring a binary mask produces grayscale values.", KernelParams),
    "median_blur": ("Median blur", ["color", "gray", "mask"], "Remove isolated specks while preserving edges and binary values.", KernelParams),
    "grayscale": ("Grayscale", ["color"], "Convert color to brightness. Color information is lost downstream.", NoParams),
    "channel": ("Extract channel", ["color"], "Inspect a color or HSV channel as a grayscale image.", ChannelParams),
    "hsv_mask": ("HSV color mask", ["color"], "Select a color band. Hue low > high wraps around red. Produces a binary mask.", HSVParams),
    "clahe": ("Local contrast", ["gray"], "Enhance local contrast with CLAHE. Useful when illumination varies.", ClaheParams),
    "otsu": ("Otsu threshold", ["gray", "mask"], "Automatically choose one brightness cutoff for the whole image.", NoParams),
    "threshold": ("Fixed threshold", ["gray", "mask"], "Keep pixels brighter than a chosen cutoff.", ThresholdParams),
    "adaptive_threshold": ("Adaptive threshold", ["gray", "mask"], "Choose brightness cutoffs from a local Gaussian neighborhood.", AdaptiveParams),
    "canny": ("Canny edges", ["gray", "mask"], "Find boundaries from brightness gradients. Produces a binary edge mask.", CannyParams),
    "invert": ("Invert", ["color", "gray", "mask"], "Reverse intensities. Swap foreground and background in a mask.", NoParams),
    "morph_open": ("Morphology · open", ["gray", "mask"], "Remove small bright regions; may remove thin features.", KernelParams),
    "morph_close": ("Morphology · close", ["gray", "mask"], "Close small dark gaps; may merge nearby objects.", KernelParams),
    "erode": ("Erode", ["gray", "mask"], "Shrink bright regions with an elliptical kernel.", KernelParams),
    "dilate": ("Dilate", ["gray", "mask"], "Expand bright regions with an elliptical kernel.", KernelParams),
    "contours": ("Filter & measure", ["mask"], "Filter external contours and measure visible objects. The next step receives the filtered mask, not the overlay.", ContourParams),
}
CATALOG.update(EXTRA_CATALOG)


class Operation(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    kind: str = Field(min_length=1, max_length=100)
    params: dict[str, int | float | bool | str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_params(self):
        if self.id == "source":
            raise ValueError("The source ID is reserved")
        if self.kind not in CATALOG:
            raise ValueError(f"Unknown operation: {self.kind}")
        self.params = CATALOG[self.kind][3].model_validate(self.params).model_dump()
        return self


class Timeline(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    fork_after: str | None = None
    rationale: str = Field(default="", max_length=2000)
    operations: list[Operation] = Field(default_factory=list, max_length=12)


class Hardware(StrictModel):
    mode: Literal["local", "clock", "relative", "calibrated"] = "local"
    cpu_name: str = Field(default="This computer", max_length=200)
    architecture: Literal["x86_64", "arm64", "other", "unknown"] = "unknown"
    target_ghz: float | None = Field(default=None, gt=0, le=10)
    host_ghz: float | None = Field(default=None, gt=0, le=10)
    relative_speed: float | None = Field(default=None, gt=.01, le=100)
    reference_local_ms: float | None = Field(default=None, gt=0, le=100000)
    reference_target_ms: float | None = Field(default=None, gt=0, le=100000)
    budget_ms: float = Field(default=33.3, gt=0, le=100000)


def resolve_paths(timelines: list[Timeline]):
    by_id = {t.id: t for t in timelines}
    if len(by_id) != len(timelines):
        raise ValueError("Pipeline IDs must be unique")
    nodes = [op.id for t in timelines for op in t.operations]
    if len(set(nodes)) != len(nodes):
        raise ValueError("Operation IDs must be unique across the workspace")
    if len(nodes) > 64:
        raise ValueError("Use at most 64 operations in a workspace")
    result, visiting = {}, set()
    def resolve(tid):
        if tid in result:
            return result[tid]
        if tid in visiting:
            raise ValueError("Branches cannot form a cycle")
        visiting.add(tid)
        timeline = by_id[tid]
        prefix = []
        if timeline.parent_id is not None:
            if timeline.parent_id not in by_id:
                raise ValueError(f"Missing parent for {timeline.name}")
            if timeline.fork_after is None:
                raise ValueError(f"Choose a fork point for {timeline.name}")
            parent_path = resolve(timeline.parent_id)
            ids = [op.id for op in parent_path]
            if timeline.fork_after != "source":
                if timeline.fork_after not in ids:
                    raise ValueError(f"The fork point for {timeline.name} is not on its parent path")
                prefix = parent_path[:ids.index(timeline.fork_after) + 1]
        elif timeline.fork_after is not None:
            raise ValueError("A root pipeline cannot have a fork point")
        result[tid] = prefix + timeline.operations
        if len(result[tid]) > 20:
            raise ValueError("A complete path may contain at most 20 operations")
        visiting.remove(tid)
        return result[tid]
    for tid in by_id:
        resolve(tid)
    return result


def output_kind(op, incoming):
    if op.kind in ('grayscale','channel','cimg_distance','sobel','top_hat','black_hat'): return 'gray'
    if op.kind in DETECTORS or op.kind in ('hsv_mask','otsu','threshold','adaptive_threshold','canny','range_mask','fill_holes'): return 'mask'
    if op.kind=='gaussian_blur' and incoming=='mask' and op.params['kernel']>1:return 'gray'
    return incoming


def path_kinds(operations, context="Pipeline"):
    incoming="color"
    kinds=[]
    for op in operations:
        if incoming not in CATALOG[op.kind][1]:
            raise ValueError(f"{context}: {CATALOG[op.kind][0]} needs {' or '.join(CATALOG[op.kind][1])}, but receives {incoming}.")
        outgoing=output_kind(op,incoming)
        kinds.append((incoming,outgoing))
        incoming=outgoing
    return kinds


def execution_plan(timelines, selected=None, resolved=None):
    """Topological node closure, including supporting branches, with shared work once."""
    resolved=resolved or resolve_paths(timelines)
    nodes={op.id:op for t in timelines for op in t.operations}
    previous={}
    for path in resolved.values():
        prior='source'
        for op in path:
            previous[op.id]=prior; prior=op.id
    dependencies={node:([prior] if prior!='source' else []) for node,prior in previous.items()}
    for op in nodes.values():
        final_ids=[]
        for reference in supporting_ids(op):
            if reference not in resolved: raise ValueError('A supporting pipeline is missing. Reconnect confirmation before removing it.')
            if not resolved[reference]: raise ValueError('A supporting pipeline needs a detector first.')
            final_id=resolved[reference][-1].id
            if final_id==previous[op.id] or final_id in final_ids:raise ValueError('Confirmation needs distinct detector results; aliases of the primary or another support do not add evidence')
            final_ids.append(final_id);dependencies[op.id].append(final_id)
    order=[]; done=set(); active=set()
    def visit(node):
        if node in done:return
        if node in active:raise ValueError('Pipeline branches and confirmation cannot form a cycle')
        active.add(node)
        for dependency in dependencies[node]:visit(dependency)
        active.remove(node);done.add(node);order.append(nodes[node])
    roots=[resolved[selected][-1].id] if selected and resolved[selected] else ([] if selected else list(nodes))
    for node in roots:visit(node)
    return order,previous,dependencies


class TimelineRunRequest(StrictModel):
    samples: list[Sample] = Field(min_length=1, max_length=12)
    timelines: list[Timeline] = Field(min_length=1, max_length=8)
    hardware: Hardware = Field(default_factory=Hardware)
    measurements: Measurements = Field(default_factory=Measurements)

    @model_validator(mode="after")
    def valid_graph(self):
        execution_plan(self.timelines)
        if len({s.id for s in self.samples}) != len(self.samples):
            raise ValueError("Image IDs must be unique")
        return self


class TimelineSuggestRequest(AnalyzeRequest):
    timelines: list[Timeline] = Field(default_factory=list, max_length=8)
    hardware: Hardware = Field(default_factory=Hardware)
    focus_timeline_id: str | None = None


class WorkspaceRequest(TimelineRunRequest):
    # A saved/uploaded family is useful before its first algorithm exists.
    timelines: list[Timeline] = Field(default_factory=list, max_length=8)


def host_info():
    ghz = None
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                ghz = round(winreg.QueryValueEx(key, "~MHz")[0] / 1000, 2)
        except OSError:
            pass
    return {"cpu_name": platform.processor() or platform.machine() or "Local CPU", "architecture": platform.machine(),
            "nominal_ghz": ghz, "threads": 1, "opencv": cv2.__version__}


def estimate_ms(local_ms, hardware: Hardware):
    if hardware.mode == "local":
        return {"ms": local_ms, "low_ms": local_ms, "high_ms": local_ms, "basis": "same machine", "estimated": False}
    factor, span, basis = None, 2.0, "Insufficient hardware information"
    if hardware.mode == "relative" and hardware.relative_speed:
        factor = 1 / hardware.relative_speed
        basis = "User-supplied single-thread speed ratio"
    elif hardware.mode == "clock" and hardware.host_ghz and hardware.target_ghz:
        factor = hardware.host_ghz / hardware.target_ghz
        span = 3.0
        basis = "GHz-only heuristic; assumes equal work per clock"
    elif hardware.mode == "calibrated" and hardware.reference_local_ms and hardware.reference_target_ms:
        factor = hardware.reference_target_ms / hardware.reference_local_ms
        span = 1.5
        basis = "Reference-workload scaling; other operations may scale differently"
    if factor is None:
        return {"ms": None, "low_ms": None, "high_ms": None, "basis": basis, "estimated": True}
    value = local_ms * factor
    return {"ms": value, "low_ms": value / span, "high_ms": value * span, "basis": basis, "estimated": True}


@dataclass
class Frame:
    image: np.ndarray
    kind: str
    preview: np.ndarray | None = None
    details: dict = field(default_factory=dict)
    regions: list = field(default_factory=list)


def contour_frame(mask, source, params, measures):
    h, w = mask.shape
    original_h, original_w = source.shape[:2]
    sx, sy = original_w / w, original_h / h
    reference = cv2.resize(source, (w, h), interpolation=cv2.INTER_AREA) if (original_w, original_h) != (w, h) else source
    overlay, accepted = reference.copy(), np.zeros_like(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not params["min_area"] <= area / (w*h) <= params["max_area"]:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        if params["reject_border"] and (x == 0 or y == 0 or x+bw >= w or y+bh >= h):
            continue
        perimeter = cv2.arcLength(contour, True)
        solidity = area / max(cv2.contourArea(cv2.convexHull(contour)), 1e-9)
        (_, _), (rw, rh), _ = cv2.minAreaRect(contour)
        aspect = max(rw,rh) / max(min(rw,rh),1e-9)
        if (4*np.pi*area / max(perimeter**2,1e-9) < params["min_circularity"] or solidity < params["min_solidity"]
                or not params["min_aspect"] <= aspect <= params["max_aspect"]):
            continue
        if len(found)>=1000:raise ValueError('More than 1,000 contours. Increase minimum area before measuring.')
        scaled = contour.astype(np.float32) * np.array([sx,sy],dtype=np.float32)
        (cx,cy), (rw,rh), angle = cv2.minAreaRect(scaled)
        unit = measures.pixels_per_unit or 1
        values = {}
        if "length" in measures.fields: values["length"] = round(max(rw,rh)/unit,3)
        if "width" in measures.fields: values["width"] = round(min(rw,rh)/unit,3)
        if "area" in measures.fields: values["area"] = round(cv2.contourArea(scaled)/unit**2,3)
        if "center" in measures.fields: values["center_px"] = [round(cx,3),round(cy,3)]
        if "angle" in measures.fields: values["angle_deg"] = round((angle+(90 if rw<rh else 0))%180,3) if max(rw,rh)/max(min(rw,rh),1e-9)>1.05 else None
        if "color" in measures.fields:
            region = np.zeros((bh,bw),np.uint8)
            cv2.drawContours(region,[contour-np.array([x,y],np.int32)],-1,255,cv2.FILLED)
            b,g,r,_ = cv2.mean(reference[y:y+bh,x:x+bw], mask=region)
            values["mean_rgb"] = [int(c+.5) for c in (r,g,b)]
        found.append(({"box": [round(x*sx,3),round(y*sy,3),round(bw*sx,3),round(bh*sy,3)],
                      "normalized_box": [x/w,y/h,bw/w,bh/h], "measurements": values},('polygon',contour)))
        cv2.drawContours(accepted,[contour],-1,255,cv2.FILLED)
        cv2.rectangle(overlay,(x,y),(x+bw,y+bh),(60,136,55),2)
    found.sort(key=lambda item:(item[0]["box"][1],item[0]["box"][0]))
    return Frame(accepted,"mask",overlay,{"detections":[item[0] for item in found],"count":len(found),"unit":measures.unit if measures.pixels_per_unit else "px","measurement_basis":"External contour; area includes holes"},[item[1] for item in found])


def apply_operation(frame: Frame, operation: Operation, source, measures):
    kind, p, im = operation.kind, operation.params, frame.image
    if frame.kind not in CATALOG[kind][1]:
        needed = " or ".join(CATALOG[kind][1])
        hint = "Move it before grayscale/color masking, or fork from a color step." if needed == "color" else "Add the appropriate grayscale or threshold operation before this step."
        raise ValueError(f"{CATALOG[kind][0]} needs {needed}; this step receives {frame.kind}. {hint}")
    if im.shape[0]*im.shape[1] > 4_200_000 and kind != "resize":
        raise ValueError("Add Resize first for images over 4.2 megapixels")
    if kind in EXTRA_CATALOG:
        from .standard_ops import STANDARD_CATALOG,apply_standard
        if kind in STANDARD_CATALOG:
            return Frame(apply_standard(im,kind,p),output_kind(operation,frame.kind))
        from .vision_ops import apply_extended
        return apply_extended(frame,operation,source,measures)
    out_kind = frame.kind
    if kind == "resize":
        scale = min(1, p["max_side"] / max(im.shape[:2]))
        size = (max(1,int(im.shape[1]*scale+.5)),max(1,int(im.shape[0]*scale+.5)))
        out = cv2.resize(im,size,interpolation=cv2.INTER_NEAREST if frame.kind=="mask" else cv2.INTER_AREA)
    elif kind == "gaussian_blur":
        out = cv2.GaussianBlur(im,(p["kernel"],p["kernel"]),0)
        if frame.kind == "mask" and p["kernel"] > 1: out_kind = "gray"
    elif kind == "median_blur": out = cv2.medianBlur(im,p["kernel"]) if p["kernel"]>1 else im.copy()
    elif kind == "grayscale": out, out_kind = cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),"gray"
    elif kind == "channel":
        channel = p["channel"]
        out = im[:,:,{"blue":0,"green":1,"red":2}[channel]].copy() if channel in ("red","green","blue") else cv2.cvtColor(im,cv2.COLOR_BGR2HSV)[:,:, {"hue":0,"saturation":1,"value":2}[channel]].copy()
        if channel == "hue": out = np.round(out.astype(np.float32)*255/179).astype(np.uint8)
        out_kind = "gray"
    elif kind == "hsv_mask":
        hsv = cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
        def band(lo,hi): return cv2.inRange(hsv,(lo,p["saturation_low"],p["value_low"]),(hi,p["saturation_high"],p["value_high"]))
        out = band(p["hue_low"],p["hue_high"]) if p["hue_low"]<=p["hue_high"] else band(p["hue_low"],179)|band(0,p["hue_high"])
        out_kind = "mask"
    elif kind == "clahe": out = cv2.createCLAHE(p["clip_limit"],(p["tile_size"],p["tile_size"])).apply(im)
    elif kind in ("otsu","threshold"):
        _,out = cv2.threshold(im,0 if kind=="otsu" else p["value"],255,cv2.THRESH_BINARY|(cv2.THRESH_OTSU if kind=="otsu" else 0))
        out_kind = "mask"
    elif kind == "adaptive_threshold":
        out = cv2.adaptiveThreshold(im,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,p["block_size"],p["constant"])
        out_kind = "mask"
    elif kind == "canny": out,out_kind = cv2.Canny(im,p["low"],p["high"]),"mask"
    elif kind == "invert": out = cv2.bitwise_not(im)
    elif kind in ("morph_open","morph_close","erode","dilate"):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(p["kernel"],p["kernel"]))
        out = cv2.morphologyEx(im,{"morph_open":cv2.MORPH_OPEN,"morph_close":cv2.MORPH_CLOSE,"erode":cv2.MORPH_ERODE,"dilate":cv2.MORPH_DILATE}[kind],kernel)
    else: return contour_frame(im,source,p,measures)
    return Frame(out,out_kind)


def preview_url(image, side=480):
    scale = min(1, side/max(image.shape[:2]))
    if scale<1: image = cv2.resize(image,(max(1,round(image.shape[1]*scale)),max(1,round(image.shape[0]*scale))))
    return data_url(image)


TIMING_NOTE = "Median of 5 warm CPU runs per operation, one thread. Decode, preview encoding, and transfer are excluded. Filter & measure includes measurements and its overlay. Pipeline totals sum medians across the complete dependency graph, including supporting branches; shared operations are counted once."
ESTIMATE_NOTE = "Target ranges are planning heuristics, not confidence intervals or guarantees. Clock-only scaling assumes equal work per clock (range ÷3 to ×3); user speed ratios use ÷2 to ×2; reference-workload scaling uses ÷1.5 to ×1.5. CPU model, architecture, and core count alone do not establish throughput. Benchmark the actual target for deployment."


def run_timelines(request: TimelineRunRequest, cancel_event=None):
    from .graph_execution import run_graph
    return run_graph(request,cancel_event)


def operation_catalog():
    return [{"kind":kind,"name":entry[0],"accepts":entry[1],"description":entry[2],"defaults":entry[3]().model_dump(),
             "fields":entry[3].model_json_schema()["properties"],"library":LIBRARIES.get(kind,'OpenCV'),
             "category":'Confirm results' if kind=='confirm' else 'Detect & measure' if kind in DETECTORS else 'Prepare & segment',
             "detector":kind in DETECTORS,"output":'gray' if kind=='cimg_distance' else 'mask' if kind in DETECTORS else None} for kind,entry in CATALOG.items()]


def timelines_from_strategies(strategies: list[Strategy]):
    timelines=[]
    for i,s in enumerate(strategies[:4]):
        prefix=f"preset{i}"
        def op(kind,params=None): return Operation(id=f"{prefix}_{len(ops)}",kind=kind,params=params or {})
        ops=[]
        if i==0:
            ops.append(op("resize"))
            if s.blur>1: ops.append(op("gaussian_blur",{"kernel":s.blur}))
            shared_id=ops[-1].id
        elif s.blur>1 and s.blur != strategies[0].blur: ops.append(op("gaussian_blur",{"kernel":s.blur}))
        if s.method=="hsv": ops.append(op("hsv_mask",{k:getattr(s,k) for k in HSVParams.model_fields}))
        else:
            ops.append(op("grayscale"))
            if s.method=="otsu": ops.append(op("otsu"))
            elif s.method=="adaptive": ops.append(op("adaptive_threshold",{"block_size":s.block_size,"constant":s.adaptive_c}))
            else: ops.append(op("canny",{"low":s.canny_low,"high":s.canny_high}))
        if s.invert: ops.append(op("invert"))
        if s.morph>0:
            # Old presets may use an even morphology size; this editor uses centered odd kernels.
            kernel=s.morph if s.morph%2 else s.morph+1
            if s.method!="canny": ops.append(op("morph_open",{"kernel":kernel}))
            ops.append(op("morph_close",{"kernel":kernel}))
        ops.append(op("contours",{k:getattr(s,k) for k in ContourParams.model_fields}))
        fork = shared_id if i else None
        if i and s.blur != strategies[0].blur: fork="preset0_0"
        timelines.append(Timeline(id=prefix,name=s.name,parent_id="preset0" if i else None,fork_after=fork,rationale=s.rationale,operations=ops))
    resolve_paths(timelines)
    return timelines
