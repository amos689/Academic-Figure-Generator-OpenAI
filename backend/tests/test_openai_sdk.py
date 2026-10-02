"""Exercise real SDK serialization without sending requests to OpenAI."""

from __future__ import annotations

import base64
import json
from email import policy
from email.parser import BytesParser
from unittest.mock import patch

import httpx2
import openai

from app.config import Settings, get_settings
from app.services.image_service import ImageService
from app.services.openai_prompt_service import OpenAIPromptService


def test_sdk_serializes_latest_models_and_max_quality(monkeypatch):
    for key in Settings.model_fields:
        if key.startswith("OPENAI_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    requests: list[httpx2.Request] = []
    image_base64 = base64.b64encode(b"mock-image").decode("ascii")

    def handle(request: httpx2.Request) -> httpx2.Response:
        request.read()
        requests.append(request)
        if request.url.path == "/v1/responses":
            return httpx2.Response(
                200,
                json={
                    "id": "resp_test",
                    "object": "response",
                    "created_at": 0,
                    "model": "gpt-6-astra",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "id": "msg_test",
                            "role": "assistant",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": '{"figures": []}',
                                    "annotations": [],
                                }
                            ],
                        }
                    ],
                },
            )
        return httpx2.Response(
            200,
            json={
                "created": 0,
                "data": [{"b64_json": image_base64}],
            },
        )

    try:
        with (
            openai.OpenAI(
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                http_client=httpx2.Client(transport=httpx2.MockTransport(handle)),
                max_retries=0,
            ) as client,
            patch("openai.OpenAI", return_value=client),
        ):
            assert OpenAIPromptService()._create_response("academic diagram") == '{"figures": []}'
            images = ImageService()
            assert images.generate_image("academic diagram")["image_base64"] == image_base64
            assert (
                images.generate_image(
                    "academic diagram",
                    reference_image_bytes=b"reference",
                    edit_instruction="pastel",
                )["image_base64"]
                == image_base64
            )
    finally:
        get_settings.cache_clear()

    assert [request.url.path for request in requests] == [
        "/v1/responses",
        "/v1/images/generations",
        "/v1/images/edits",
    ]
    prompt_body = json.loads(requests[0].content)
    assert prompt_body["model"] == "gpt-6-astra"
    assert prompt_body["reasoning"]["effort"] == "max"
    assert prompt_body["text"]["format"]["strict"] is True
    generation_body = json.loads(requests[1].content)
    assert generation_body["model"] == "gpt-image-2.5-sunburst"
    assert generation_body["quality"] == "max"

    headers = f"Content-Type: {requests[2].headers['content-type']}\r\n\r\n".encode()
    multipart = BytesParser(policy=policy.default).parsebytes(headers + requests[2].content)
    fields = {
        part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
        for part in multipart.iter_parts()
    }
    assert fields["model"] == b"gpt-image-2.5-sunburst"
    assert fields["quality"] == b"max"
    assert fields["image"] == b"reference"
