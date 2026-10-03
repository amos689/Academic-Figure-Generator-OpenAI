import asyncio

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import Job, Project
from app.services.job_service import JobRunner, enqueue_job


async def add_job(sessions, key=None):
    async with sessions() as db:
        if not await db.get(Project, "project"):
            db.add(Project(id="project", name="Test"))
            await db.flush()
        job, created = await enqueue_job(
            db,
            project_id="project",
            kind="prompt",
            payload={"input": "fixture"},
            idempotency_key=key,
        )
        await db.commit()
        return job, created


async def test_idempotent_submission(sessions):
    first, created = await add_job(sessions, "test-request")
    second, repeated = await add_job(sessions, "test-request")
    assert created and not repeated and first.id == second.id
    async with sessions() as db:
        with pytest.raises(AppException) as error:
            await enqueue_job(
                db, project_id="project", kind="image", payload={}, idempotency_key="test-request"
            )
        assert error.value.status_code == 409


async def test_claim_and_complete_only_once(sessions):
    job, _ = await add_job(sessions)
    runner = JobRunner(sessions)
    calls = []

    async def handler(current, db):
        assert current.status == "running"
        calls.append(current.id)
        return {"prompt_ids": ["fixture"]}

    runner.register("prompt", handler)
    claimed = await runner.claim()
    assert await runner.claim() is None
    await runner.execute(claimed)
    async with sessions() as db:
        complete = await db.get(Job, job.id)
        assert complete.status == "succeeded"
        assert complete.result == {"prompt_ids": ["fixture"]}
    assert calls == [job.id]


async def test_recovery_never_resubmits_running_jobs(sessions):
    job, _ = await add_job(sessions)
    runner = JobRunner(sessions)
    await runner.claim()
    await runner.recover_interrupted()
    assert await runner.claim() is None
    async with sessions() as db:
        recovered = await db.get(Job, job.id)
        assert recovered.status == "interrupted"
        assert "unknown" in recovered.error


async def test_worker_concurrency_is_bounded_and_failures_are_private(sessions):
    for _ in range(4):
        await add_job(sessions)
    active = peak = 0
    runner = JobRunner(sessions, concurrency=2)

    async def handler(job, db):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1
        raise RuntimeError("private paper and key")

    runner.register("prompt", handler)
    await runner.start()
    for _ in range(100):
        async with sessions() as db:
            statuses = list(await db.scalars(select(Job.status)))
        if statuses == ["failed"] * 4:
            break
        await asyncio.sleep(0.02)
    await runner.stop()
    assert 1 <= peak <= 2
    async with sessions() as db:
        jobs = list(await db.scalars(select(Job)))
        assert all(job.status == "failed" and "private" not in job.error for job in jobs)
