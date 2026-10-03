import logging

import httpx
import pytest
from fastapi import FastAPI

from app.core.exceptions import register_exception_handlers
from app.core.middleware import setup_middleware
from app.core.privacy import SecretRedactingFilter, public_error, redact_secrets


@pytest.mark.asyncio
async def test_origin_and_host_protect_local_mutations():
    app = FastAPI()
    setup_middleware(app)

    @app.post("/mutate")
    async def mutate():
        return {"ok": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://localhost"
    ) as client:
        assert (
            await client.post("/mutate", headers={"Origin": "https://evil.test"})
        ).status_code == 403
        assert (await client.post("/mutate", headers={"Origin": "null"})).status_code == 403
        assert (
            await client.post("/mutate", headers={"Host": "rebind.evil.test"})
        ).status_code == 400
        assert (
            await client.post("/mutate", headers={"Origin": "http://localhost:5173"})
        ).status_code == 200
        assert (await client.post("/mutate")).status_code == 200


@pytest.mark.asyncio
async def test_internal_error_does_not_return_traceback_or_secret():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/error")
    async def error():
        raise RuntimeError("Bearer private-fixture-token /private/local/path")

    transport = httpx.ASGITransport(app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/error")
    assert response.status_code == 500
    assert "private" not in response.text
    assert "traceback" not in response.text


def test_provider_diagnostics_are_sanitized():
    assert "fixture-secret" not in redact_secrets("Bearer fixture-secret")
    assert "sensitive" not in public_error(RuntimeError("sensitive request body"))
    record = logging.LogRecord(
        "test", logging.ERROR, "", 0, "Failed: %s", ("Bearer fixture-secret",), None
    )
    assert SecretRedactingFilter().filter(record)
    assert "fixture-secret" not in record.getMessage()
