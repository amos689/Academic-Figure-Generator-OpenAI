from sqlalchemy import select

from app.models import Document, Job
from app.services.job_handlers import register_handlers
from app.services.job_service import JobRunner
from app.services.local_storage_service import LocalStorageService


async def test_document_upload_commits_before_processing_and_keeps_names_unique(
    api_client, sessions
):
    project = (await api_client.post("/api/v1/projects/", json={"name": "Public fixture"})).json()
    responses = []
    for content in [b"# Method\nAn original pipeline.", b"# Results\nNo numerical claims."]:
        response = await api_client.post(
            f"/api/v1/projects/{project['id']}/documents",
            files={"file": ("../../paper.txt", content, "text/plain")},
        )
        assert response.status_code == 201, response.text
        assert response.json()["parse_status"] == "pending"
        assert response.json()["original_filename"] == "paper.txt"
        responses.append(response.json())
    async with sessions() as db:
        docs = list(await db.scalars(select(Document)))
        assert len({doc.storage_path for doc in docs}) == 2
        assert all(LocalStorageService().file_exists(doc.storage_path) for doc in docs)
    runner = JobRunner(sessions)
    register_handlers(runner)
    for _ in range(2):
        await runner.execute(await runner.claim())
    for document in responses:
        result = await api_client.get(f"/api/v1/documents/{document['id']}")
        assert result.json()["parse_status"] == "completed"
        job = await api_client.get(f"/api/v1/jobs/{document['job_id']}")
        assert job.json()["status"] == "succeeded"


async def test_cancel_queued_and_retry_failed_are_idempotent(api_client, sessions):
    project = (await api_client.post("/api/v1/projects/", json={"name": "Fixture"})).json()
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("paper.txt", b"Document", "text/plain")},
    )
    job_id = response.json()["job_id"]
    cancelled = await api_client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    assert (await api_client.post(f"/api/v1/jobs/{job_id}/cancel")).status_code == 409
    async with sessions() as db:
        job = await db.get(Job, job_id)
        job.status = "interrupted"
        await db.commit()
    first = (await api_client.post(f"/api/v1/jobs/{job_id}/retry")).json()
    second = (await api_client.post(f"/api/v1/jobs/{job_id}/retry")).json()
    assert first["id"] == second["id"] and first["retry_of"] == job_id
    assert "payload" not in first


async def test_database_and_raw_uploads_are_not_public(api_client):
    assert (await api_client.get("/data/app.db")).status_code == 404
    assert (await api_client.get("/data/uploads/paper.txt")).status_code == 404
