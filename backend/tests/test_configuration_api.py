from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import httpx
import httpx2
import openai
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api.v1.configuration import router
from app.config import Settings, get_settings
from app.dependencies import get_db
from app.models import Image, Job, Project
from app.services.configuration_service import CHECK_TIMEOUT_SECONDS, ConfigurationService
from app.services.style_service import style_presets

SECRET = "sk-configuration-private-fixture-value"
_OPENAI_CLIENT = openai.OpenAI


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    get_settings.cache_clear()

    def forbidden_client(**kwargs):
        raise AssertionError("Unexpected provider access; this test must install a mocked SDK")

    monkeypatch.setattr(openai, "OpenAI", forbidden_client)
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(sessions):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def database():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://localhost"
    ) as client:
        yield client


def fake_sdk(monkeypatch, retrieve=None, construction_error=None, close_error=None):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs, threading.get_ident()))
            if construction_error:
                raise construction_error
            self.models = SimpleNamespace(retrieve=self.retrieve)

        def retrieve(self, model):
            calls.append(("retrieve", model, threading.get_ident()))
            return retrieve(model) if retrieve else SimpleNamespace(id=model)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append(("close", None, threading.get_ident()))
            if close_error:
                raise close_error

    monkeypatch.setattr(openai, "OpenAI", Client)
    return calls


@pytest.mark.asyncio
async def test_effective_configuration_is_passive_secret_free_and_matches_styles(
    client, monkeypatch
):
    monkeypatch.setenv("OPENAI_API_BASE", "https://proxy.example.test/v1/")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "configured-text")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "configured-image")
    monkeypatch.setenv("OPENAI_TEXT_REASONING_EFFORT", "high")
    monkeypatch.setenv("OPENAI_TEXT_MAX_OUTPUT_TOKENS", "8192")
    monkeypatch.setenv("OPENAI_IMAGE_QUALITY", "high")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "100")
    monkeypatch.setenv("MAX_CONCURRENT_JOBS", "3")
    get_settings.cache_clear()
    response = await client.get("/api/v1/configuration")
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "api_key_configured": True,
        "api_key_source": "environment",
        "api_base": "https://proxy.example.test/v1",
        "text_model": "configured-text",
        "text_reasoning_effort": "high",
        "text_max_output_tokens": 8192,
        "image_model": "configured-image",
        "image_quality": "high",
        "max_upload_size_mb": 100,
        "max_concurrent_jobs": 3,
        "styles": style_presets(),
        "profiles": [
            {
                "id": "quality",
                "name": "Quality",
                "text_reasoning_effort": "high",
                "image_quality": "high",
            },
            {
                "id": "draft",
                "name": "Draft",
                "text_reasoning_effort": "medium",
                "image_quality": "medium",
            },
        ],
        "usage_summary": {
            "jobs_completed": 0,
            "jobs_failed": 0,
            "input_tokens": None,
            "output_tokens": None,
            "image_count": 0,
            "duration_ms": None,
        },
    }
    assert (await client.get("/api/v1/styles")).json() == data["styles"]
    assert "instructions" not in response.text
    assert SECRET not in response.text and SECRET[:12] not in response.text
    assert "OPENAI_API_KEY" not in response.text and "SECRET_KEY" not in response.text
    assert not any("prefix" in key for key in data)
    assert (await client.get("/api/v1/configuration/check")).status_code == 405


@pytest.mark.asyncio
async def test_usage_counts_recorded_outcomes_without_inventing_provider_totals(client, sessions):
    async with sessions() as db:
        project = Project(name="Configuration counts")
        db.add(project)
        await db.flush()
        for index, status in enumerate(
            ["succeeded", "succeeded", "failed", "interrupted", "cancelled", "queued", "running"]
        ):
            db.add(
                Job(
                    project_id=project.id,
                    kind="prompt",
                    status=status,
                    payload={"private": SECRET},
                    request_hash=str(index) * 64,
                    result={
                        "usage": {"input_tokens": 123, "output_tokens": 456},
                        "duration_ms": 789,
                    },
                )
            )
        for status in ["completed", "completed", "failed", "pending"]:
            db.add(
                Image(
                    project_id=project.id,
                    generation_status=status,
                    generation_metadata={"usage": {"input_tokens": 17}},
                    generation_duration_ms=33,
                )
            )
        await db.commit()
    response = await client.get("/api/v1/configuration")
    assert response.json()["usage_summary"] == {
        "jobs_completed": 2,
        "jobs_failed": 1,
        "input_tokens": None,
        "output_tokens": None,
        "image_count": 2,
        "duration_ms": None,
    }
    assert SECRET not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environment,backend,root,source",
    [
        ("environment-secret", "backend-secret", "root-secret", "environment"),
        ("", "backend-secret", "root-secret", "backend_dotenv"),
        ("  ", "  ", "root-secret", "root_dotenv"),
        ("", "", "", "missing"),
    ],
)
async def test_endpoint_reports_actual_key_source(
    client, monkeypatch, tmp_path, environment, backend, root, source
):
    root_path, backend_path = tmp_path / "root.env", tmp_path / "backend.env"
    root_path.write_text(f'OPENAI_API_KEY="{root}"\n', encoding="utf-8")
    backend_path.write_text(f'OPENAI_API_KEY="{backend}"\n', encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", (root_path, backend_path))
    monkeypatch.setenv("OPENAI_API_KEY", environment)
    get_settings.cache_clear()
    response = await client.get("/api/v1/configuration")
    data = response.json()
    assert data["api_key_source"] == source
    assert data["api_key_configured"] is (source != "missing")
    assert not any(
        value.strip() in response.text for value in (environment, backend, root) if value.strip()
    )


@pytest.mark.asyncio
async def test_check_only_retrieves_models_with_bounded_sdk_settings_off_loop(client, monkeypatch):
    calls = fake_sdk(monkeypatch)
    loop_thread = threading.get_ident()
    response = await client.post("/api/v1/configuration/check", json={"api_key": "ignored-key"})
    assert response.status_code == 200
    settings = get_settings()
    assert response.json() == {
        "ok": True,
        "models": [
            {"model": settings.OPENAI_TEXT_MODEL, "accessible": True},
            {"model": settings.OPENAI_IMAGE_MODEL, "accessible": True},
        ],
    }
    assert calls[0][1] == {
        "api_key": SECRET,
        "base_url": settings.OPENAI_API_BASE,
        "timeout": CHECK_TIMEOUT_SECONDS,
        "max_retries": 0,
    }
    assert [call[0] for call in calls] == ["client", "retrieve", "retrieve", "close"]
    assert all(call[2] != loop_thread for call in calls)
    assert SECRET not in response.text and "ignored-key" not in response.text


@pytest.mark.asyncio
async def test_missing_key_does_not_construct_sdk(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    get_settings.cache_clear()
    calls = fake_sdk(monkeypatch)
    response = await client.post("/api/v1/configuration/check")
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["detail"] == "No API key is configured."
    assert all(not item["accessible"] for item in response.json()["models"])
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,phrase",
    [
        (401, "Access denied"),
        (403, "Access denied"),
        (404, "unavailable"),
        (429, "rate limit"),
        (500, "could not be verified"),
    ],
)
async def test_provider_errors_are_sanitized_and_other_model_is_still_checked(
    client,
    monkeypatch,
    caplog,
    status,
    phrase,
):
    class ProviderError(Exception):
        status_code = status

    def retrieve(model):
        if model == get_settings().OPENAI_TEXT_MODEL:
            raise ProviderError(f"Authorization: Bearer {SECRET}; body=private-provider-payload")

    calls = fake_sdk(monkeypatch, retrieve)
    response = await client.post("/api/v1/configuration/check")
    data = response.json()
    assert data["ok"] is False and phrase in data["detail"]
    assert [item["accessible"] for item in data["models"]] == [False, True]
    assert len([call for call in calls if call[0] == "retrieve"]) == 2
    assert SECRET not in response.text + caplog.text
    assert SECRET[:12] not in response.text + caplog.text
    assert "private-provider-payload" not in response.text + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "constructor", "close"])
async def test_timeout_setup_and_cleanup_failures_are_private(client, monkeypatch, failure):
    error = TimeoutError(SECRET) if failure == "timeout" else RuntimeError(SECRET)

    def retrieve(model):
        raise error

    fake_sdk(
        monkeypatch,
        retrieve=retrieve if failure == "timeout" else None,
        construction_error=error if failure == "constructor" else None,
        close_error=error if failure == "close" else None,
    )
    response = await client.post("/api/v1/configuration/check")
    assert response.json()["ok"] is False
    assert SECRET not in response.text
    if failure == "timeout":
        assert "timed out" in response.json()["detail"]


@pytest.mark.asyncio
async def test_identical_configured_models_are_checked_once(client, monkeypatch):
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "shared-model")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "shared-model")
    get_settings.cache_clear()
    calls = fake_sdk(monkeypatch)
    data = (await client.post("/api/v1/configuration/check")).json()
    assert data == {"ok": True, "models": [{"model": "shared-model", "accessible": True}]}
    assert len([call for call in calls if call[0] == "retrieve"]) == 1


@pytest.mark.asyncio
async def test_slow_sdk_does_not_block_event_loop(monkeypatch):
    started, release = threading.Event(), threading.Event()

    def retrieve(model):
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test release did not arrive")

    fake_sdk(monkeypatch, retrieve)
    task = asyncio.create_task(ConfigurationService().check_connectivity())
    try:
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.005)
        assert started.is_set()
        assert not task.done()
        await asyncio.sleep(0)
    finally:
        release.set()
        result = await task
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_real_sdk_transport_only_sends_model_gets_without_retries(client, monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx2.Response(429, json={"error": {"message": SECRET}})
        return httpx2.Response(
            200,
            json={
                "id": get_settings().OPENAI_IMAGE_MODEL,
                "object": "model",
                "created": 0,
                "owned_by": "test",
            },
        )

    def sdk_client(**kwargs):
        return _OPENAI_CLIENT(
            **kwargs, http_client=httpx2.Client(transport=httpx2.MockTransport(handle))
        )

    monkeypatch.setattr(openai, "OpenAI", sdk_client)
    response = await client.post("/api/v1/configuration/check")
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert [item["accessible"] for item in response.json()["models"]] == [False, True]
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", f"/v1/models/{get_settings().OPENAI_TEXT_MODEL}"),
        ("GET", f"/v1/models/{get_settings().OPENAI_IMAGE_MODEL}"),
    ]
    assert all(
        request.extensions["timeout"]["read"] == CHECK_TIMEOUT_SECONDS for request in requests
    )
    assert SECRET not in response.text
