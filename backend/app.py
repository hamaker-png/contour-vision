import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.requests import ClientDisconnect

from . import ai, timeline_ai
from .local_settings import server_key,stored_key,public_mode,save_local_key
from .models import StrictModel
from .engine import decode_image, run_experiment
from .exporter import export_cpp
from .timeline_exporter import TimelineExportRequest, export_timeline
from .cpu_work import run_cpu, run_async, check_cancelled
from .server_policy import (MAX_BODY_BYTES, PublicAdmission, configured_hosts,
                            request_origin_error, security_headers)
from .models import AnalyzeRequest, DiscoveryRequest, ExperimentRequest, ExportRequest, Strategy
from .timelines import (TimelineRunRequest, TimelineSuggestRequest, host_info, operation_catalog,
                        resolve_paths, run_timelines, timelines_from_strategies, WorkspaceRequest)

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Contour · CPU Vision Workbench", docs_url="/api/docs", redoc_url=None)
work_lock = asyncio.Semaphore(1)
admission = PublicAdmission()


@app.middleware("http")
async def local_requests(request: Request, call_next):
    def error(detail, status, headers=None):
        return security_headers(JSONResponse({"detail": detail}, status_code=status, headers=headers))
    origin_error = request_origin_error(request)
    if origin_error:
        return error(origin_error, 403)
    key = request.headers.get("x-openai-key", "")
    if len(key) > 512 or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in key):
        return error("Use a single API key without whitespace", 400)
    entered = False
    try:
        if request.method == "POST":
            if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                return error("Send application/json", 415)
            try:
                declared = int(request.headers.get("content-length", "0"))
                if declared < 0:
                    raise ValueError()
            except ValueError:
                return error("Invalid content length", 400)
            if declared > MAX_BODY_BYTES:
                return error("This image batch is too large. Use fewer or smaller images.", 413)
            if public_mode():
                refused = admission.enter()
                if refused:
                    status, detail, retry = refused
                    return error(detail, status, {"Retry-After": retry})
                entered = True
            size, chunks = 0, []
            async with asyncio.timeout(30):
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_BODY_BYTES:
                        return error("This image batch is too large. Use fewer or smaller images.", 413)
                    chunks.append(chunk)
            request._body = b"".join(chunks)
        return security_headers(await call_next(request))
    except TimeoutError:
        return error("The upload took too long. Retry with fewer or smaller images.", 408)
    except ClientDisconnect:
        return Response(status_code=499)
    except Exception:
        # Do not return or log exception messages: they can contain payloads/keys.
        return error("The server could not complete this request. Retry or simplify the input.", 500)
    finally:
        if entered:
            admission.leave()


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # FastAPI's default errors include the rejected input, potentially an image/key.
    errors = []
    for item in exc.errors():
        location = item["loc"]
        message = item["msg"]
        if public_mode():
            # Custom validators can interpolate the bad value into their message.
            if item["type"] == "value_error":
                message = "Invalid value or incompatible pipeline configuration"
            if item["type"] == "extra_forbidden":
                location = (*location[:-1], "<unexpected field>")
        errors.append({"loc": location, "msg": message, "type": item["type"]})
    return JSONResponse({"detail": errors}, status_code=422)


@app.exception_handler(ValidationError)
async def invalid_model_output(request, exc):
    return JSONResponse({"detail": "The supplied configuration or AI response was invalid. Review it and retry."}, status_code=400)


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get("/api/health")
def health():
    return {"ok": True, "server_key": bool(server_key()), "local_key_saved":bool(stored_key()),
            "local_key_storage":not public_mode(), "cpu_only": True, "public_mode":public_mode(),
            "processing_location":"server" if public_mode() else "local",
            "key_policy":"per_request" if public_mode() else "local_optional",
            "max_request_bytes":MAX_BODY_BYTES}

class LocalKeyRequest(StrictModel):
    key: str = ''
    remember: bool = True

@app.post('/api/local-settings')
def local_settings(request:LocalKeyRequest):
    save_local_key(request.key,request.remember)
    return {'server_key':bool(server_key()),'local_key_saved':bool(stored_key())}


@app.post("/api/analyze")
async def analyze(request: DiscoveryRequest, http_request: Request, x_openai_key: str = Header(default="")):
    if not (x_openai_key or server_key()):raise ValueError('Add an OpenAI API key in AI settings.')
    content=await run_cpu(http_request,work_lock,ai.image_content,request)
    if isinstance(content,Response):return content
    return await run_async(http_request, ai.discover, request, x_openai_key,content)


@app.post("/api/plan")
async def plan(request: AnalyzeRequest, http_request: Request, x_openai_key: str = Header(default="")):
    if not (x_openai_key or server_key()):raise ValueError('Add an OpenAI API key in AI settings.')
    content=await run_cpu(http_request,work_lock,ai.image_content,request)
    if isinstance(content,Response):return content
    return await run_async(http_request, ai.plan, request, x_openai_key,content)


@app.post("/api/experiment")
async def experiment(request: ExperimentRequest, http_request: Request):
    return await run_cpu(http_request,work_lock,run_experiment,request.samples,request.strategies,request.measurements,request.tune)


class ReviewRequest(AnalyzeRequest):
    strategies: list[Strategy]


@app.post("/api/review")
async def review(request: ReviewRequest, http_request: Request, x_openai_key: str = Header(default="")):
    if not (x_openai_key or server_key()):raise ValueError("Add an OpenAI API key in AI settings.")
    if not 1 <= len(request.strategies) <= 6:
        raise HTTPException(400, "Review between one and six strategies")
    # Keep held-out images out of the AI's view, including transform review.
    training = [s for s in request.samples if s.split == "train"]
    def prepare_review(cancel_event=None):
        result=run_experiment(training,request.strategies,request.measurements,False,cancel_event=cancel_event)
        content=ai.image_content(request,cancel_event=cancel_event)
        return result,content
    prepared=await run_cpu(http_request,work_lock,prepare_review)
    if isinstance(prepared,Response):return prepared
    result,content=prepared
    return await run_async(http_request,ai.review,request,x_openai_key,result,content)


@app.post("/api/export")
def export(request: ExportRequest):
    return Response(export_cpp(request), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="cpu-detector.zip"'})


@app.get("/api/examples")
def examples():
    entries = []
    for filename in ("manifest.json", "critic-fixtures.json", "vision-fixtures.json",
                     "object-tests-photos.json", "object-tests-a.json", "object-tests-b.json"):
        path = ROOT / "examples" / filename
        if path.exists():
            entries.extend(json.loads(path.read_text(encoding="utf-8")))
    return entries


@app.get("/api/timelines/catalog")
def catalog():
    return {"operations": operation_catalog(), "host": host_info()}


@app.get("/api/timelines/presets/{example_id}")
def presets(example_id: str):
    example = next((e for e in examples() if e["id"] == example_id), None)
    if not example:
        raise HTTPException(404, "Unknown example")
    if "pipelines" in example:
        from .timelines import Timeline
        pipelines = [Timeline.model_validate(value) for value in example["pipelines"]]
        for pipeline in pipelines:
            TimelineExportRequest(timelines=pipelines, selected_timeline_id=pipeline.id)
        return {"timelines": [pipeline.model_dump() for pipeline in pipelines]}
    return {"timelines": [t.model_dump() for t in timelines_from_strategies([Strategy.model_validate(s) for s in example["strategies"]])]}


@app.post("/api/timelines/run")
async def run_graph(request: TimelineRunRequest, http_request: Request):
    return await run_cpu(http_request, work_lock, run_timelines, request)


from .optimizer import OptimizeRequest, optimize

@app.post('/api/timelines/optimize')
async def optimize_graph(request: OptimizeRequest, http_request: Request):
    return await run_cpu(http_request,work_lock,optimize,request)


@app.post("/api/timelines/validate")
async def validate_graph(request: WorkspaceRequest, http_request: Request):
    def validate_images(cancel_event=None):
        pixels = 0
        for sample in request.samples:
            check_cancelled(cancel_event)
            try:
                image = decode_image(sample.data)
            except ValueError as exc:
                raise ValueError(f"{sample.name}: {exc}") from exc
            check_cancelled(cancel_event)
            pixels += image.shape[0] * image.shape[1]
            if pixels > 40_000_000:
                raise ValueError("This batch exceeds 40 megapixels")
        return request.model_dump()
    return await run_cpu(http_request, work_lock, validate_images)


@app.post('/api/timelines/export')
def export_graph(request: TimelineExportRequest):
    return Response(export_timeline(request),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="pipeline-detector.zip"'})


@app.post("/api/timelines/suggest")
async def suggest_graph(request: TimelineSuggestRequest, http_request: Request, x_openai_key: str = Header(default="")):
    if not (x_openai_key or server_key()):
        raise ValueError("Add an OpenAI API key in AI settings. Local pipelines work without a key.")
    resolve_paths(request.timelines)
    training = [s for s in request.samples if s.split == "train"]
    experiment = None
    if training:
        from .ai_evidence import prepare_evidence
        experiment = await run_cpu(http_request, work_lock, prepare_evidence, request)
        if isinstance(experiment, Response):
            return experiment
    return await run_async(http_request, timeline_ai.suggest, request, x_openai_key, experiment)


@app.get("/detector")
def detector():
    return FileResponse(ROOT / "static" / "detector.html")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "explorer.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/examples", StaticFiles(directory=ROOT / "examples", check_dir=False), name="examples")
