import json

from app.models import Project
from app.services.job_handlers import register_handlers
from app.services.job_service import JobRunner
from app.services.openai_prompt_service import OpenAIPromptService
from app.services.prompt_service import PromptService


async def test_legacy_prompt_derives_grounded_spec_without_overwriting_edits(
    api_client, sessions, monkeypatch
):
    async with sessions() as db:
        db.add(Project(id="spec-project", name="Fixture"))
        await db.flush()
        prompt = (
            await PromptService(db).create_prompts_from_figures(
                "spec-project", None, [{"prompt": "Input flows to output."}]
            )
        )[0]
        await db.commit()
    result = {
        "title": "Flow",
        "nodes": [
            {
                "id": "input",
                "label": "Input",
                "sources": [{"section_index": 0, "quote": "Input flows to output."}],
            }
        ],
        "edges": [],
        "groups": [],
    }
    monkeypatch.setattr(OpenAIPromptService, "_create_response", lambda *_: json.dumps(result))
    first = (await api_client.post(f"/api/v1/prompts/{prompt.id}/spec-jobs")).json()
    duplicate = (await api_client.post(f"/api/v1/prompts/{prompt.id}/spec-jobs")).json()
    assert duplicate["id"] == first["id"]
    runner = JobRunner(sessions)
    register_handlers(runner)
    await runner.execute(await runner.claim())
    updated = (await api_client.get(f"/api/v1/prompts/{prompt.id}")).json()
    assert updated["figure_spec"]["nodes"][0]["label"] == "Input"
    assert updated["revision"] == 2
    second = (await api_client.post(f"/api/v1/prompts/{prompt.id}/spec-jobs")).json()
    await api_client.put(
        f"/api/v1/prompts/{prompt.id}", json={"edited_prompt": "New private draft"}
    )
    await runner.execute(await runner.claim())
    job = (await api_client.get(f"/api/v1/jobs/{second['id']}")).json()
    assert job["status"] == "succeeded" and job["result"]["applied"] is False
    current = (await api_client.get(f"/api/v1/prompts/{prompt.id}")).json()
    assert current["active_prompt"] == "New private draft" and current["figure_spec"] is None
