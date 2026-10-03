from xml.etree import ElementTree as ET

import pymupdf
import pytest

from app.models import Project
from app.services.job_handlers import register_handlers
from app.services.job_service import JobRunner
from app.services.process_service import stop_offline_workers
from app.services.prompt_service import PromptService


@pytest.mark.parametrize("format", ["svg", "pdf", "drawio"])
async def test_export_downloads_are_editable_and_snapshot_revision(api_client, sessions, format):
    async with sessions() as db:
        db.add(Project(id="export-project", name="Fixture"))
        await db.flush()
        prompts = await PromptService(db).create_prompts_from_figures(
            "export-project",
            None,
            [
                {
                    "prompt": "A simple pipeline",
                    "figure_spec": {
                        "title": "Evidence pipeline",
                        "nodes": [
                            {"id": "input", "label": "Source data"},
                            {"id": "output", "label": "Verified figure"},
                        ],
                        "edges": [
                            {
                                "id": "flow",
                                "source": "input",
                                "target": "output",
                                "label": "Transform",
                            }
                        ],
                        "groups": [],
                    },
                }
            ],
        )
        await db.commit()
        prompt_id = prompts[0].id
    submitted = await api_client.post(
        f"/api/v1/prompts/{prompt_id}/exports",
        json={"format": format, "width": 1200, "idempotency_key": f"export-{format}"},
    )
    assert submitted.status_code == 202, submitted.text
    await api_client.put(
        f"/api/v1/prompts/{prompt_id}", json={"edited_prompt": "Changed after export was queued"}
    )
    runner = JobRunner(sessions)
    register_handlers(runner)
    try:
        await runner.execute(await runner.claim())
    finally:
        await stop_offline_workers()
    records = (await api_client.get("/api/v1/projects/export-project/exports")).json()
    assert records[0]["prompt_revision"] == 1
    assert records[0]["generation_status"] == "completed"
    assert records[0]["width_px"] == 1200
    download = await api_client.get(f"/api/v1/exports/{records[0]['id']}/download")
    assert download.status_code == 200
    assert download.headers["x-content-type-options"] == "nosniff"
    if format == "pdf":
        with pymupdf.open(stream=download.content, filetype="pdf") as pdf:
            assert "Source data" in pdf[0].get_text()
            assert pdf[0].get_images() == []
    else:
        root = ET.fromstring(download.content)
        assert root.tag.endswith("svg") if format == "svg" else root.tag == "mxfile"
        assert b"Source data" in download.content


async def test_raster_only_prompts_are_not_falsely_exported(api_client, sessions):
    async with sessions() as db:
        db.add(Project(id="no-spec", name="Fixture"))
        await db.flush()
        prompt = (
            await PromptService(db).create_prompts_from_figures(
                "no-spec", None, [{"prompt": "Illustration"}]
            )
        )[0]
        await db.commit()
    response = await api_client.post(f"/api/v1/prompts/{prompt.id}/exports", json={"format": "svg"})
    assert response.status_code == 400
    assert "FigureSpec" in response.json()["detail"]
