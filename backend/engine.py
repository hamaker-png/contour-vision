"""Bounded OpenCV strategies. The C++ template implements this same pipeline."""
import base64
import struct
import io
import statistics
import time

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Measurements, Sample, Strategy
from .cpu_work import check_cancelled

cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)
MAX_SIDE = 1280
Image.MAX_IMAGE_PIXELS = 24_000_000


def decode_image(data: str) -> np.ndarray:
    if not data.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")):
        raise ValueError("Use a PNG, JPEG, or WebP image")
    try:
        raw = base64.b64decode(data.split(",", 1)[1], validate=True)
        if len(raw) > 8_000_000:
            raise ValueError("Images must be under 8 MB")
        with Image.open(io.BytesIO(raw)) as im:
            if im.width * im.height > 24_000_000:
                raise ValueError("Images must be under 24 megapixels")
            if im.mode in ("I", "I;16", "I;16B", "I;16L", "F"):
                raise ValueError("Use 8-bit PNG, JPEG, or WebP images to match the C++ runtime")
            if im.mode == "CMYK":
                raise ValueError("Convert CMYK JPEG images to RGB before use; their color decoding differs across runtimes")
            im = ImageOps.exif_transpose(im)
            rgba = im.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            background.alpha_composite(rgba)
            return cv2.cvtColor(np.array(background.convert("RGB")), cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, SyntaxError, struct.error, base64.binascii.Error, Image.DecompressionBombError) as exc:
        raise ValueError("The image could not be decoded") from exc


def data_url(image: np.ndarray, thumbnail=False) -> str:
    if thumbnail and max(image.shape[:2]) > 720:
        scale = 720 / max(image.shape[:2])
        image = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Could not encode preview")
    return "data:image/png;base64," + base64.b64encode(encoded).decode()


def working_image(image):
    h, w = image.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h, w))
    # Half-up rounding is reproduced by std::lround in the C++ export.
    size = (max(1, int(w * scale + 0.5)), max(1, int(h * scale + 0.5)))
    small = cv2.resize(image, size, interpolation=cv2.INTER_AREA) if scale < 1 else image
    return small, w / size[0], h / size[1]


def transform(image: np.ndarray, s: Strategy):
    blurred = cv2.GaussianBlur(image, (s.blur, s.blur), 0) if s.blur > 1 else image.copy()
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    if s.method == "hsv":
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        def band(lo, hi):
            return cv2.inRange(hsv, (lo, s.saturation_low, s.value_low),
                               (hi, s.saturation_high, s.value_high))
        mask = band(s.hue_low, s.hue_high) if s.hue_low <= s.hue_high else (
            band(s.hue_low, 179) | band(0, s.hue_high))
        feature = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    elif s.method == "otsu":
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        feature = gray
    elif s.method == "adaptive":
        mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, s.block_size, s.adaptive_c)
        feature = gray
    else:
        mask = cv2.Canny(gray, s.canny_low, s.canny_high)
        feature = gray
    if s.invert:
        mask = cv2.bitwise_not(mask)
    raw = mask.copy()
    if s.morph > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (s.morph, s.morph))
        if s.method != "canny":
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return feature, raw, mask


def detect(image: np.ndarray, s: Strategy, measures: Measurements):
    small, sx, sy = working_image(image)
    feature, raw, mask = transform(small, s)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = small.shape[:2]
    detections = []
    accepted = np.zeros_like(mask)
    overlay = small.copy()
    for contour in contours:
        area = cv2.contourArea(contour)
        if not s.min_area <= area / (h * w) <= s.max_area:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        if s.reject_border and (x == 0 or y == 0 or x + bw >= w or y + bh >= h):
            continue
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / max(perimeter * perimeter, 1e-9)
        hull_area = cv2.contourArea(cv2.convexHull(contour))
        solidity = area / max(hull_area, 1e-9)
        rect = cv2.minAreaRect(contour)
        side1, side2 = rect[1]
        aspect = max(side1, side2) / max(min(side1, side2), 1e-9)
        if circularity < s.min_circularity or solidity < s.min_solidity or not s.min_aspect <= aspect <= s.max_aspect:
            continue
        # Measure in original pixel coordinates, accounting for rounded resize dimensions.
        original_contour = contour.astype(np.float32) * np.array([sx, sy], dtype=np.float32)
        (cx, cy), (rw, rh), angle = cv2.minAreaRect(original_contour)
        if rw < rh:
            angle += 90
        angle %= 180
        unit_scale = measures.pixels_per_unit or 1.0
        measured = {}
        if "length" in measures.fields:
            measured["length"] = round(max(rw, rh) / unit_scale, 3)
        if "width" in measures.fields:
            measured["width"] = round(min(rw, rh) / unit_scale, 3)
        if "area" in measures.fields:
            measured["area"] = round(cv2.contourArea(original_contour) / unit_scale**2, 3)
        if "angle" in measures.fields:
            # A near-square rectangle has no stable long axis. OpenCV versions can
            # choose axes 90 degrees apart for the same circular/symmetric object.
            measured["angle_deg"] = round(angle, 3) if max(rw, rh) / max(min(rw, rh), 1e-9) > 1.05 else None
        if "center" in measures.fields:
            measured["center_px"] = [round(cx, 3), round(cy, 3)]
        if "color" in measures.fields:
            region = np.zeros_like(mask)
            cv2.drawContours(region, [contour], -1, 255, cv2.FILLED)
            b, g, r, _ = cv2.mean(small, mask=region)
            rgb = [int(v + 0.5) for v in [r, g, b]]
            measured["mean_rgb"] = rgb
            measured["color_hex"] = "#" + "".join(f"{v:02x}" for v in rgb)
        detections.append({"box": [round(x * sx, 3), round(y * sy, 3), round(bw * sx, 3), round(bh * sy, 3)],
                           "normalized_box": [x / w, y / h, bw / w, bh / h],
                           "measurements": measured})
        cv2.drawContours(accepted, [contour], -1, 255, cv2.FILLED)
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (65, 144, 50), 2)
    detections.sort(key=lambda d: (d["box"][1], d["box"][0]))
    return {"detections": detections, "count": len(detections),
            "unit": measures.unit if measures.pixels_per_unit else "px",
            "stages": {"input": small, "feature": feature, "threshold": raw,
                       "cleaned": mask, "accepted": accepted, "detections": overlay}}


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    intersection = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))
    return intersection / max(aw * ah + bw * bh - intersection, 1e-12)


def counts(detections, sample: Sample):
    truth = [[b.x, b.y, b.width, b.height] for b in sample.boxes]
    pairs = sorted([(iou(d["normalized_box"], b), i, j) for i, d in enumerate(detections)
                    for j, b in enumerate(truth)], reverse=True)
    used_d, used_t = set(), set()
    for overlap, i, j in pairs:
        if overlap >= 0.5 and i not in used_d and j not in used_t:
            used_d.add(i)
            used_t.add(j)
    return len(used_d), len(detections) - len(used_d), len(truth) - len(used_t)


def metrics(results, samples, split):
    triples = [counts(r["detections"], s) for r, s in zip(results, samples) if s.labeled and s.split == split]
    if not triples:
        return None
    tp, fp, fn = map(sum, zip(*triples))
    return {"tp": tp, "fp": fp, "fn": fn, "images": len(triples),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "negative_images": sum(s.labeled and s.split == split and not s.boxes for s in samples)}


def contrast(mask, sample):
    if not sample.labeled or not sample.boxes:
        return None
    h, w = mask.shape
    region = np.zeros((h, w), dtype=bool)
    for b in sample.boxes:
        region[int(b.y*h):int((b.y+b.height)*h), int(b.x*w):int((b.x+b.width)*w)] = True
    if not region.any() or region.all():
        return None
    return round(float((mask[region] > 0).mean() - (mask[~region] > 0).mean()), 3)


def candidates(s):
    variants = [s]
    for morph in [0, 3, 5]:
        if morph != s.morph:
            variants.append(s.model_copy(update={"morph": morph}))
    return variants


def run_experiment(samples, strategies, measures, tune=True, cancel_event=None):
    images = []
    total_pixels = 0
    for sample in samples:
        check_cancelled(cancel_event)
        image = decode_image(sample.data)
        check_cancelled(cancel_event)
        total_pixels += image.shape[0] * image.shape[1]
        if total_pixels > 40_000_000:
            raise ValueError("This batch exceeds 40 megapixels. Use fewer or smaller images.")
        images.append(image)
    train_indices = [i for i, s in enumerate(samples) if s.split == "train"]
    if not train_indices:
        raise ValueError("Add at least one training image")
    labeled_train = any(s.labeled and s.split == "train" for s in samples)
    ranked = []
    for index, base in enumerate(strategies):
        check_cancelled(cancel_event)
        variants = candidates(base) if tune and labeled_train else [base]
        best, best_score = base, (-1.0, -float("inf"))
        for strategy in variants:
            trials = []
            for i in train_indices:
                check_cancelled(cancel_event)
                trials.append(detect(images[i], strategy, measures))
            score = metrics(trials, [samples[i] for i in train_indices], "train")
            # Validation images never participate in parameter or strategy selection.
            score_key = (score["f1"] if score and score["f1"] is not None else -1,
                         -score["fp"] if score else 0)
            if score_key > best_score:
                best, best_score = strategy, score_key
        results = []
        times = []
        for image, sample in zip(images, samples):
            check_cancelled(cancel_event)
            # One warmup, then three measured CPU runs. Preview encoding excluded.
            result = detect(image, best, measures)
            for _ in range(3):
                check_cancelled(cancel_event)
                start = time.perf_counter()
                result = detect(image, best, measures)
                times.append((time.perf_counter() - start) * 1000)
            result["separation"] = contrast(result["stages"]["cleaned"], sample)
            check_cancelled(cancel_event)
            result["stages"] = {key: data_url(value, thumbnail=True) for key, value in result["stages"].items()}
            result.update({"sample_id": sample.id, "name": sample.name, "split": sample.split})
            results.append(result)
        ranked.append({"id": str(index), "strategy": best.model_dump(), "results": results,
                       "train": metrics(results, samples, "train"), "validation": metrics(results, samples, "validation"),
                       "latency_ms": round(statistics.median(times), 2), "variants_tested": len(variants)})
    def rank(item):
        m = item["train"]
        return (m["f1"] if m and m["f1"] is not None else -1, -m["fp"] if m else 0)
    ranked.sort(key=rank, reverse=True)
    check_cancelled(cancel_event)
    return {"strategies": ranked, "ranked_by": "training labels" if labeled_train else "proposal order (unscored)",
            "note": "F1 uses one-to-one boxes at IoU ≥ 0.5. Small sample scores are not a reliability guarantee. "
                    "Validation is excluded from AI planning and tuning; repeated manual choices can still overfit it."}
