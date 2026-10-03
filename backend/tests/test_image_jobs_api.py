import base64
import io

from PIL import Image as PILImage
from sqlalchemy import select

from app.models import Image, Job
from app.services.image_service import ImageService
from app.services.job_handlers import register_handlers
from app.services.job_service import JobRunner


def png(mode="RGB"):
    output = io.BytesIO()
    PILImage.new(mode, (32, 32)).save(output, format="PNG")
    return output.getvalue()


def mock_generation(monkeypatch, calls):
    def generate(self, **kwargs):
        calls.append(kwargs)
        return {
            "image_base64": base64.b64encode(png()).decode(),
            "width": 32,
            "height": 32,
            "duration_ms": 20,
            "format": "png",
            "generation_metadata": {
                "model": "fixture-image-model",
                "quality": self.quality,
                "usage": {"input_tokens": 3, "output_tokens": 5},
            },
        }

    monkeypatch.setattr(ImageService, "generate_image", generate)


async def test_direct_generation_is_durable_idempotent_and_downloadable(
    api_client, sessions, monkeypatch
):
    calls = []
    mock_generation(monkeypatch, calls)
    body = {
        "prompt": "Original educational diagram",
        "style_preset": "pastel",
        "color_scheme": "teal-coral",
        "idempotency_key": "image-fixture",
    }
    first = await api_client.post("/api/v1/images/generate-direct", json=body)
    assert first.status_code == 202, first.text
    duplicate = await api_client.post("/api/v1/images/generate-direct", json=body)
    assert duplicate.json()["id"] == first.json()["id"]
    assert calls == []
    runner = JobRunner(sessions)
    register_handlers(runner)
    await runner.execute(await runner.claim())
    image_id = first.json()["id"]
    image = (await api_client.get(f"/api/v1/images/{image_id}")).json()
    assert image["generation_status"] == "completed"
    assert image["generation_model"] == "fixture-image-model"
    assert "#00695C" in calls[0]["prompt"] and "pastel" in calls[0]["prompt"]
    assert (await api_client.get(image["download_url"])).content == png()
    provenance = (await api_client.get(f"/api/v1/images/{image_id}/provenance")).json()
    assert provenance["generation_metadata"]["usage"]["output_tokens"] == 5
    assert (
        await api_client.patch(
            f"/api/v1/images/{image_id}", json={"favorite": True, "selected": True}
        )
    ).json()["selected"] is True
    async with sessions() as db:
        assert len(list(await db.scalars(select(Image)))) == 1


async def test_mask_edit_retains_ancestry_and_rejects_invalid_mask(
    api_client, sessions, monkeypatch
):
    calls = []
    mock_generation(monkeypatch, calls)
    first = (
        await api_client.post(
            "/api/v1/images/generate-direct", json={"prompt": "Original", "style_preset": "pastel"}
        )
    ).json()
    runner = JobRunner(sessions)
    register_handlers(runner)
    await runner.execute(await runner.claim())
    invalid = await api_client.post(
        f"/api/v1/images/{first['id']}/edit",
        data={"edit_instruction": "Larger labels"},
        files={"mask_image": ("mask.png", png(), "image/png")},
    )
    assert invalid.status_code == 422
    edited = await api_client.post(
        f"/api/v1/images/{first['id']}/edit",
        data={"edit_instruction": "Larger labels"},
        files={"mask_image": ("mask.png", png("RGBA"), "image/png")},
    )
    assert edited.status_code == 202, edited.text
    await runner.execute(await runner.claim())
    result = (await api_client.get(f"/api/v1/images/{edited.json()['id']}")).json()
    assert result["parent_image_id"] == first["id"] and result["style_preset"] == "pastel"
    assert calls[-1]["mask_image_bytes"] == png("RGBA")
    assert calls[-1]["reference_image_bytes"] == png()
    assert calls[-1]["edit_instruction"] == "Larger labels"
