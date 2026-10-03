from app.models import Project
from app.services.prompt_service import PromptService


async def create_fixture(sessions):
    async with sessions() as db:
        db.add(Project(id="revision-project", name="Fixture"))
        await db.flush()
        prompts = await PromptService(db).create_prompts_from_figures(
            "revision-project",
            None,
            [{"prompt": "Original content", "title": "Fixture"}],
            "fixture-model",
        )
        await db.commit()
        return prompts[0].id


async def test_edit_restore_and_stale_revision(api_client, sessions):
    prompt_id = await create_fixture(sessions)
    update = await api_client.put(
        f"/api/v1/prompts/{prompt_id}",
        json={"edited_prompt": "Updated content", "expected_revision": 1},
    )
    assert update.status_code == 200, update.text
    assert update.json()["revision"] == 2
    conflict = await api_client.put(
        f"/api/v1/prompts/{prompt_id}",
        json={"edited_prompt": "Stale content", "expected_revision": 1},
    )
    assert conflict.status_code == 409
    restored = await api_client.post(f"/api/v1/prompts/{prompt_id}/restore", json={"revision": 1})
    assert restored.json()["revision"] == 3
    assert restored.json()["active_prompt"] == "Original content"
    revisions = (await api_client.get(f"/api/v1/prompts/{prompt_id}/revisions")).json()
    assert [item["revision"] for item in revisions] == [3, 2, 1]
    assert revisions[1]["prompt_text"] == "Updated content"


async def test_text_edits_invalidate_stale_specs_and_numbering_keeps_growing(api_client, sessions):
    prompt_id = await create_fixture(sessions)
    spec = {"nodes": [{"id": "input", "label": "Input"}], "edges": [], "groups": []}
    first = await api_client.put(
        f"/api/v1/prompts/{prompt_id}",
        json={"edited_prompt": "Original content", "figure_spec": spec},
    )
    assert first.json()["figure_spec"] is not None
    second = await api_client.put(
        f"/api/v1/prompts/{prompt_id}", json={"edited_prompt": "Change diagram semantics"}
    )
    assert second.json()["figure_spec"] is None
    async with sessions() as db:
        prompts = await PromptService(db).create_prompts_from_figures(
            "revision-project", None, [{"prompt": "Second", "figure_number": 1}]
        )
        assert prompts[0].figure_number == 2
