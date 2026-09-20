import asyncio
import importlib
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.server_policy import PublicAdmission
from test_family_workflow import sample

module = importlib.import_module("backend.app")


@pytest.fixture
def public(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTOUR_PUBLIC", "1")
    monkeypatch.setenv("CONTOUR_ALLOWED_HOSTS", "contour.example")
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    monkeypatch.delenv("CONTOUR_MAX_ACTIVE_POSTS", raising=False)
    monkeypatch.delenv("CONTOUR_POSTS_PER_MINUTE", raising=False)
    monkeypatch.setattr(module, "admission", PublicAdmission())
    from backend import local_settings
    monkeypatch.setattr(local_settings, "KEY_FILE", tmp_path / "settings.json")
    local_settings.KEY_FILE.write_text('{"openai_api_key":"private-saved-key"}')
    monkeypatch.setenv("OPENAI_API_KEY", "private-server-key")
    return TestClient(module.app, base_url="https://contour.example")


def test_public_health_and_credentials_are_isolated(public):
    response = public.get("/api/health")
    assert response.status_code == 200
    assert response.json()["public_mode"] and response.json()["processing_location"] == "server"
    assert not response.json()["server_key"] and not response.json()["local_key_saved"]
    assert not response.json()["local_key_storage"]
    assert "private-" not in response.text
    response = public.post("/api/local-settings", json={"key": "visitor-key", "remember": True})
    assert response.status_code == 400
    from backend.local_settings import KEY_FILE
    assert "private-saved-key" in KEY_FILE.read_text() and "visitor-key" not in KEY_FILE.read_text()
    response = public.post("/api/analyze", json={"samples": [sample().model_dump()]})
    assert response.status_code == 400 and "API key" in response.text


def test_render_exact_host_and_origin(public, monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "contour-abc.onrender.com")
    with TestClient(module.app, base_url="https://contour-abc.onrender.com") as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health", headers={"origin": "https://contour-abc.onrender.com"}).status_code == 200
    for headers in [
        {"host": "evil.example"},
        {"host": "contour.example.evil.example"},
        {"host": "user@contour.example"},
        {"origin": "https://evil.example"},
        {"origin": "https://contour.example.evil.example"},
        {"origin": "http://contour.example"},
        {"origin": "null"},
        {"sec-fetch-site": "cross-site"},
    ]:
        response = public.get("/api/health", headers=headers)
        assert response.status_code == 403, headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"
    assert public.get("/api/health", headers={"host": "evil.example", "x-forwarded-host": "contour.example"}).status_code == 403
    assert public.get("/api/health", headers={"origin": "https://contour.example"}).status_code == 200


def test_unconfigured_public_host_fails_closed_and_loopback_health_works(public, monkeypatch):
    monkeypatch.delenv("CONTOUR_ALLOWED_HOSTS")
    assert public.get("/api/health").status_code == 403
    with TestClient(module.app, base_url="http://127.0.0.1:8000") as client:
        assert client.get("/api/health").status_code == 200


def test_json_only_size_and_key_bounds(public, monkeypatch):
    assert public.post("/api/local-settings", content="key=secret").status_code == 415
    assert public.post("/api/local-settings", json={}, headers={"x-openai-key": "secret value"}).status_code == 400
    assert public.post("/api/local-settings", json={}, headers={"x-openai-key": "s" * 513}).status_code == 400
    monkeypatch.setattr(module, "MAX_BODY_BYTES", 128)
    assert public.post("/api/local-settings", json={"key": "x" * 200}).status_code == 413
    # No trusted Content-Length: the actual streamed bytes are also bounded.
    response = public.post("/api/local-settings", content=iter([b" " * 80, b" " * 80]), headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_validation_and_unexpected_errors_do_not_echo_payloads(public, monkeypatch):
    secret = "private-image-and-key-marker"
    response = public.post("/api/analyze", json={"samples": [{"data": secret}], "description": secret * 300})
    assert response.status_code == 422 and secret not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])
    response = public.post("/api/timelines/export", json={
        "timelines": [{"id": "main", "name": "Main", "operations": [{"id": "bad", "kind": secret}]}],
        "selected_timeline_id": "main", secret: True})
    assert response.status_code == 422 and secret not in response.text
    monkeypatch.setattr(module, "run_cpu", AsyncMock(side_effect=RuntimeError(secret)))
    response = public.post("/api/analyze", json={"samples": [sample().model_dump()]}, headers={"x-openai-key": "visitor-key"})
    assert response.status_code == 500 and secret not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert module.admission.active == 0


def test_public_rate_limit_and_read_routes_stay_available(public, monkeypatch):
    monkeypatch.setenv("CONTOUR_POSTS_PER_MINUTE", "2")
    for _ in range(2):
        assert public.post("/api/local-settings", json={}).status_code == 400
    response = public.post("/api/local-settings", json={})
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    assert public.get("/api/health").status_code == 200
    assert public.get("/").status_code == 200
    assert module.admission.active == 0


def test_busy_public_request_rejected_before_reading_its_body(public, monkeypatch):
    monkeypatch.setenv("CONTOUR_MAX_ACTIVE_POSTS", "1")
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        consumed = False
        async def prepare(*args):
            started.set()
            await release.wait()
            return []
        async def second_body():
            nonlocal consumed
            consumed = True
            yield b"{}"
        monkeypatch.setattr(module, "run_cpu", prepare)
        monkeypatch.setattr(module.ai, "discover", AsyncMock(return_value={"ok": True}))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="https://contour.example") as client:
            first = asyncio.create_task(client.post("/api/analyze", json={"samples": [sample().model_dump()]}, headers={"x-openai-key": "visitor-key"}))
            await asyncio.wait_for(started.wait(), 2)
            second = await client.post("/api/local-settings", content=second_body(), headers={"content-type": "application/json"})
            assert second.status_code == 503 and second.headers["retry-after"] == "2"
            assert not consumed and module.admission.active == 1
            release.set()
            assert (await asyncio.wait_for(first, 2)).status_code == 200
            assert module.admission.active == 0
    asyncio.run(scenario())


def test_classic_cpu_work_has_cooperative_cancellation():
    import threading
    from backend.engine import run_experiment
    from backend.cpu_work import WorkCancelled
    from backend.models import Measurements, Strategy
    stop = threading.Event()
    stop.set()
    with pytest.raises(WorkCancelled):
        run_experiment([sample()], [Strategy(name="test", method="otsu")], Measurements(), cancel_event=stop)


def test_public_disconnect_retains_admission_until_native_worker_exits(public, monkeypatch):
    import threading
    from backend.cpu_work import check_cancelled
    from test_cpu_cancellation import request as graph_request
    async def scenario():
        queued = asyncio.Queue()
        await queued.put({"type": "http.request", "body": json.dumps(graph_request().model_dump()).encode(), "more_body": False})
        started, cancelled, release = threading.Event(), threading.Event(), threading.Event()
        def work(request, cancel_event=None):
            started.set()
            assert cancel_event.wait(3)
            cancelled.set()
            assert release.wait(3)
            check_cancelled(cancel_event)
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                 "http_version": "1.1", "method": "POST", "scheme": "https",
                 "path": "/api/timelines/run", "raw_path": b"/api/timelines/run",
                 "query_string": b"", "root_path": "",
                 "headers": [(b"host", b"contour.example"), (b"content-type", b"application/json")],
                 "client": ("127.0.0.1", 1234), "server": ("contour.example", 443)}
        async def send(message): pass
        monkeypatch.setattr(module, "work_lock", asyncio.Semaphore(1))
        monkeypatch.setattr(module, "run_timelines", work)
        running = asyncio.create_task(module.app(scope, queued.get, send))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert module.admission.active == 1
            queued.put_nowait({"type": "http.disconnect"})
            assert await asyncio.to_thread(cancelled.wait, 2)
            assert module.admission.active == 1 and module.work_lock._value == 0
        finally:
            release.set()
            await asyncio.wait_for(running, 3)
        assert module.admission.active == 0 and module.work_lock._value == 1
    asyncio.run(scenario())


def test_public_launcher_is_single_worker_and_ignores_proxy_identity(monkeypatch):
    from backend import serve
    monkeypatch.setenv("CONTOUR_PUBLIC", "1")
    monkeypatch.setenv("CONTOUR_ALLOWED_HOSTS", "contour.example")
    monkeypatch.setenv("PORT", "8123")
    monkeypatch.setenv("WEB_CONCURRENCY", "32")
    monkeypatch.setattr(serve, "library", lambda: object())
    observed = {}
    monkeypatch.setattr(serve.uvicorn, "run", lambda app, **kwargs: observed.update(app=app, **kwargs))
    serve.main()
    assert observed["host"] == "0.0.0.0" and observed["port"] == 8123
    assert observed["workers"] == 1 and observed["limit_concurrency"] == 16
    assert not observed["proxy_headers"] and not observed["access_log"]
    monkeypatch.delenv("CONTOUR_PUBLIC")
    with pytest.raises(SystemExit, match="run.py"):
        serve.main()
