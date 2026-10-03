from app.models import Document, Project
from app.services.job_handlers import register_handlers
from app.services.job_service import JobRunner
from app.services.openai_prompt_service import OpenAIPromptService


async def test_prompt_job_uses_explicit_document_and_style(api_client, sessions, monkeypatch):
    async with sessions() as db:
        db.add(Project(id="prompt-project", name="Fixture", style_preset="pastel"))
        await db.flush()
        for index in range(2):
            db.add(
                Document(
                    id=f"doc-{index}",
                    project_id="prompt-project",
                    original_filename="fixture.txt",
                    file_type="txt",
                    file_size_bytes=10,
                    storage_path=f"uploads/doc-{index}.txt",
                    parse_status="completed",
                    sections=[
                        {
                            "index": 0,
                            "title": f"Method {index}",
                            "content": f"Original method {index}",
                        }
                    ],
                )
            )
        await db.commit()
    calls = []

    async def generate(self, **kwargs):
        calls.append((self.style_preset, kwargs))
        return {
            "figures": [{"title": "Flow", "prompt": "Detailed prompt", "figure_spec": None}],
            "model": "fixture-model",
            "generation_metadata": {"usage": {"input_tokens": 12}},
            "duration_ms": 3,
        }

    monkeypatch.setattr(OpenAIPromptService, "generate_figure_prompts", generate)
    request = {
        "document_id": "doc-0",
        "section_indices": [0],
        "max_figures": 1,
        "idempotency_key": "prompt-request",
    }
    first = await api_client.post("/api/v1/projects/prompt-project/prompt-jobs", json=request)
    assert first.status_code == 202, first.text
    second = await api_client.post("/api/v1/projects/prompt-project/prompt-jobs", json=request)
    assert second.json()["id"] == first.json()["id"]
    assert calls == []
    runner = JobRunner(sessions)
    register_handlers(runner)
    await runner.execute(await runner.claim())
    assert calls[0][0] == "pastel"
    assert calls[0][1]["sections"][0]["content"] == "Original method 0"
    prompts = (await api_client.get("/api/v1/projects/prompt-project/prompts")).json()
    assert prompts[0]["generation_model"] == "fixture-model"
    assert prompts[0]["document_id"] == "doc-0"
    assert prompts[0]["generation_metadata"]["palette"]["primary"]
    job = (await api_client.get(f"/api/v1/jobs/{first.json()['id']}")).json()
    assert job["result"]["prompt_ids"] == [prompts[0]["id"]]
    assert (
        await api_client.post(
            "/api/v1/projects/prompt-project/prompt-jobs",
            json={**request, "document_id": "missing"},
        )
    ).status_code == 400
    assert (
        await api_client.post(
            "/api/v1/projects/prompt-project/prompt-jobs", json={**request, "section_indices": []}
        )
    ).status_code == 400
    assert (
        await api_client.post(
            "/api/v1/projects/prompt-project/prompt-jobs", json={**request, "max_figures": 9}
        )
    ).status_code == 422
