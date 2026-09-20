import asyncio
import base64
import io
import json
import struct
import zipfile
import zlib
from pathlib import Path
from unittest.mock import patch

import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import ai
from backend.app import app
from backend.engine import counts, data_url, decode_image, detect, metrics, run_experiment
from backend.exporter import export_cpp
from backend.models import AnalyzeRequest, Box, ExportRequest, Measurements, Sample, Strategy

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "examples/manifest.json").read_text())
ALL = Measurements(fields=["length", "width", "area", "angle", "color", "center"])


def fixture(example):
    raw = (ROOT / "examples" / example["filename"]).read_bytes()
    return Sample(id=example["id"], name=example["filename"], data="data:image/png;base64,"+base64.b64encode(raw).decode(),
                  labeled=True, boxes=example["boxes"])


def rectangle():
    image = np.full((240, 320, 3), 255, np.uint8)
    cv2.rectangle(image, (70, 80), (230, 140), (0, 0, 255), -1)
    return image


RED = Strategy(name="red", method="hsv", hue_low=170, hue_high=7, blur=1, morph=0)


def test_analytical_measurements_and_selected_fields():
    result = detect(rectangle(), RED, ALL)
    assert result["count"] == 1
    m = result["detections"][0]["measurements"]
    assert m["length"] == pytest.approx(160, abs=.01)
    assert m["width"] == pytest.approx(60, abs=.01)
    assert m["area"] == pytest.approx(9600, abs=.01)
    assert m["center_px"] == [150, 110]
    assert m["mean_rgb"] == [255, 0, 0]
    assert m["angle_deg"] == 0
    calibrated = detect(rectangle(), RED, Measurements(fields=["length","width","area"], pixels_per_unit=10, unit="mm"))
    assert calibrated["unit"] == "mm"
    assert calibrated["detections"][0]["measurements"] == {"length":16, "width":6, "area":96}
    assert detect(rectangle(), RED, Measurements(fields=[]))["detections"][0]["measurements"] == {}


def test_rotation_and_original_coordinate_scale():
    image = np.full((1600, 2000, 3), 255, np.uint8)
    box = cv2.boxPoints(((1000,800),(700,180),32)).astype(np.int32)
    cv2.fillPoly(image, [box], (0,0,255))
    m = detect(image, RED, ALL)["detections"][0]["measurements"]
    assert m["length"] == pytest.approx(700, abs=5)
    assert m["width"] == pytest.approx(180, abs=5)
    assert m["angle_deg"] == pytest.approx(32, abs=1)
    assert m["center_px"] == pytest.approx([1000,800],abs=2)


def test_symmetric_object_has_no_misleading_angle():
    image = np.full((200,200,3),255,np.uint8)
    cv2.circle(image,(100,100),40,(0,0,255),-1)
    result = detect(image,RED,ALL)
    assert result["count"] == 1
    assert result["detections"][0]["measurements"]["angle_deg"] is None


@pytest.mark.parametrize("example", MANIFEST, ids=lambda e:e["id"])
def test_internet_images_against_manual_boxes(example):
    sample = fixture(example)
    result = run_experiment([sample], [Strategy(**s) for s in example["strategies"]], ALL)
    best = result["strategies"][0]
    assert best["train"]["f1"] == 1
    assert best["results"][0]["count"] == len(example["boxes"])
    assert best["validation"] is None
    for stage in best["results"][0]["stages"].values():
        assert decode_image(stage).size > 0


@pytest.mark.parametrize("gain", [.65, .85, 1.1])
def test_photo_brightness_perturbations(gain):
    sample = fixture(MANIFEST[0])
    image = np.clip(decode_image(sample.data).astype(np.float32)*gain, 0, 255).astype(np.uint8)
    result = detect(image, Strategy(**MANIFEST[0]["strategies"][0]), ALL)
    assert counts(result["detections"], sample) == (4, 0, 0)


def test_empty_negative_is_not_reported_as_perfect_recall():
    sample = Sample(id="empty", name="blank", data=data_url(np.full((200,200,3),255,np.uint8)), labeled=True)
    result = run_experiment([sample], [RED], ALL)
    m = result["strategies"][0]["train"]
    assert m["tp"] == m["fp"] == m["fn"] == 0
    assert m["recall"] is None and m["f1"] is None
    assert m["negative_images"] == 1


def test_validation_does_not_change_tuning_or_ranking():
    train = Sample(id="train", name="red", data=data_url(rectangle()), labeled=True,
                   boxes=[Box(x=70/320,y=80/240,width=161/320,height=61/240)])
    validation = train.model_copy(update={"id":"held-out","split":"validation","boxes":[]})
    strategies = [RED, Strategy(name="wrong green",method="hsv",hue_low=35,hue_high=80)]
    first = run_experiment([train],strategies,ALL)
    second = run_experiment([train,validation],strategies,ALL)
    assert [s["strategy"] for s in first["strategies"]] == [s["strategy"] for s in second["strategies"]]
    assert second["strategies"][0]["validation"]["fp"] == 1
    assert second["strategies"][0]["validation"]["recall"] is None


def test_one_to_one_box_matching_and_false_positives():
    sample = Sample(id="1",name="1",data="",labeled=True,boxes=[Box(x=.1,y=.1,width=.2,height=.2)])
    duplicate = [{"normalized_box":[.1,.1,.2,.2]}]*2
    assert counts(duplicate,sample) == (1,1,0)


def test_alpha_composited_to_white():
    raw = np.zeros((20,20,4),np.uint8)
    raw[5:15,5:15] = [0,255,0,255]
    image = decode_image(data_url(raw))
    assert list(image[0,0]) == [255,255,255]
    assert list(image[10,10]) == [0,255,0]


@pytest.mark.parametrize('exif', [b'II*', b'II*\0\x08'])
def test_truncated_exif_is_a_decode_error_and_validation_returns_400(exif):
    # Real short TIFF headers previously escaped as SyntaxError / struct.error.
    from PIL import Image
    stream = io.BytesIO()
    Image.new('RGB', (2, 2), 'white').save(stream, 'PNG')
    png = stream.getvalue()
    chunk = (struct.pack('>I', len(exif)) + b'eXIf' + exif
             + struct.pack('>I', zlib.crc32(b'eXIf' + exif) & 0xffffffff))
    data = 'data:image/png;base64,' + base64.b64encode(png[:33] + chunk + png[33:]).decode()
    with pytest.raises(ValueError, match='could not be decoded'):
        decode_image(data)
    with TestClient(app) as client:
        response = client.post('/api/timelines/validate', json={
            'samples': [{'id': 'broken', 'name': 'broken-exif.png', 'data': data}],
            'timelines': []})
    assert response.status_code == 400
    assert 'broken-exif.png' in response.json()['detail']


@pytest.mark.parametrize('progressive', [False, True])
def test_cmyk_jpeg_requires_explicit_rgb_conversion(progressive):
    from PIL import Image
    stream = io.BytesIO()
    Image.new('CMYK', (13, 17), (25, 60, 125, 30)).save(stream, 'JPEG', progressive=progressive)
    data = 'data:image/jpeg;base64,' + base64.b64encode(stream.getvalue()).decode()
    with pytest.raises(ValueError, match='Convert CMYK JPEG images to RGB'):
        decode_image(data)


def test_export_zip_has_only_standalone_cpp_files_and_no_key():
    archive = export_cpp(ExportRequest(strategy=RED,measurements=ALL,description='A target with "quotes"'))
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert set(z.namelist()) == {"detector.cpp","CMakeLists.txt","config.json","README.md"}
        cpp = z.read("detector.cpp").decode()
        assert "GENERATED_CONSTANTS" not in cpp
        assert "constexpr bool measure_color = true" in cpp
        assert "http" not in cpp and "OPENAI" not in cpp
        assert json.loads(z.read("config.json"))["strategy"]["hue_low"] == 170


def test_request_validation_and_local_origin():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/api/examples").json()[0]["id"] == "red-candies"
        assert client.post("/api/export",json={},headers={"origin":"https://untrusted.example"}).status_code == 403
        assert client.post("/api/export",json={"strategy":{"name":"bad","method":"exec"}}).status_code == 422
        assert client.post("/api/export",json={"strategy":{"name":"bad","method":"hsv","blur":2}}).status_code == 422
        sample = fixture(MANIFEST[0])
        response = client.post("/api/experiment",json={"samples":[sample.model_dump()],"strategies":[MANIFEST[0]["strategies"][0]]})
        assert response.status_code == 200
        assert response.json()["strategies"][0]["results"][0]["count"] == 4


def test_ai_payload_excludes_validation_and_store_is_false(monkeypatch):
    sample = fixture(MANIFEST[0])
    held = fixture(MANIFEST[1]).model_copy(update={"split":"validation"})
    request = AnalyzeRequest(samples=[sample,held],description="red candies")
    captured = {}
    async def post(self,url,**kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(200,json={"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"observations":"Four red candies", "important_features":["red hue"], "questions":["Can the background change?"],"limitations":["Small sample"]})}]}]})
    monkeypatch.setattr(httpx.AsyncClient,"post",post)
    result = asyncio.run(ai.discover(request,"test-placeholder-not-a-key"))
    assert result["questions"]
    assert captured["store"] is False
    assert captured["text"]["format"]["strict"] is True
    assert "green-shapes" not in json.dumps(captured)
    assert "test-placeholder" not in json.dumps(captured)
    assert sum(c["type"]=="input_image" for c in captured["input"][0]["content"]) == 1


def test_ai_refusal_and_auth_error_are_actionable(monkeypatch):
    async def post(self,url,**kwargs):
        return httpx.Response(401,json={"error":"private provider details"})
    monkeypatch.setattr(httpx.AsyncClient,"post",post)
    with pytest.raises(ValueError,match="key was rejected"):
        asyncio.run(ai.discover(AnalyzeRequest(samples=[fixture(MANIFEST[0])],description="red candies"),"test-placeholder"))


def test_schema_has_required_fields_for_all_properties():
    schema = ai.PLAN["properties"]["strategies"]["items"]
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    assert "default" not in json.dumps(schema)


def test_mocked_plan_execute_review_and_export_workflow(monkeypatch):
    sample = fixture(MANIFEST[0])
    held = fixture(MANIFEST[1]).model_copy(update={"split":"validation"})
    emitted = []
    async def post(self,url,**kwargs):
        payload = kwargs["json"]
        emitted.append(payload)
        name = payload["text"]["format"]["name"]
        if name == "detector_plan":
            result = {"summary":"Use red hue", "strategies":[Strategy(**MANIFEST[0]["strategies"][0]).model_dump()], "limitations":["Validate other lighting"]}
        else:
            result = {"assessment":"The mask exposes four red targets.", "recommended_strategy":"Red hue + contours", "next_steps":["Add independent negative examples"]}
        return httpx.Response(200,json={"status":"completed","output":[{"content":[{"type":"output_text","text":json.dumps(result)}]}]})
    monkeypatch.setattr(httpx.AsyncClient,"post",post)
    brief = AnalyzeRequest(samples=[sample,held],description="Red candies",answers="Color is important; ignore orange.").model_dump()
    headers={"X-OpenAI-Key":"test-placeholder-not-a-key"}
    with TestClient(app) as client:
        plan = client.post("/api/plan",json=brief,headers=headers)
        assert plan.status_code == 200
        strategies = plan.json()["strategies"]
        experiments = client.post("/api/experiment",json={"samples":brief["samples"],"strategies":strategies})
        assert experiments.json()["strategies"][0]["train"]["f1"] == 1
        review = client.post("/api/review",json={**brief,"strategies":strategies},headers=headers)
        assert review.status_code == 200
        assert review.json()["recommended_strategy"] == strategies[0]["name"]
        export = client.post("/api/export",json={"strategy":strategies[0]})
        assert export.status_code == 200 and export.content.startswith(b"PK")
    assert len(emitted) == 2
    for payload in emitted:
        assert "green-shapes" not in json.dumps(payload)
    # Review includes original training image, cleaned mask, and actual overlay.
    assert sum(c["type"]=="input_image" for c in emitted[1]["input"][0]["content"]) == 3
