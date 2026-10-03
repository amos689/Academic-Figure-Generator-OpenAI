"""Persist before dispatch; never automatically repeat a started provider call."""

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import AppException, NotFoundException
from app.core.privacy import public_error
from app.models.document import Document
from app.models.image import Image
from app.models.job import Job

logger = logging.getLogger(__name__)
Handler = Callable[[Job, AsyncSession], Awaitable[dict]]
FailureHandler = Callable[[Job, AsyncSession, str, str], Awaitable[None]]


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def enqueue_job(
    db: AsyncSession,
    *,
    project_id: str,
    kind: str,
    payload: dict,
    resource_id: str | None = None,
    idempotency_key: str | None = None,
    retry_of: str | None = None,
) -> tuple[Job, bool]:
    fingerprint = hashlib.sha256(
        json.dumps(
            {"project": project_id, "kind": kind, "payload": payload}, sort_keys=True
        ).encode()
    ).hexdigest()
    if idempotency_key:
        existing = (
            await db.execute(select(Job).where(Job.idempotency_key == idempotency_key))
        ).scalar_one_or_none()
        if existing:
            if existing.request_hash != fingerprint:
                raise AppException(
                    409, "Idempotency key was already used for another request", "CONFLICT"
                )
            return existing, False
    job = Job(
        project_id=project_id,
        kind=kind,
        payload=payload,
        resource_id=resource_id,
        request_hash=fingerprint,
        idempotency_key=idempotency_key,
        retry_of=retry_of,
    )
    try:
        async with db.begin_nested():
            db.add(job)
            await db.flush()
    except IntegrityError:
        if not idempotency_key:
            raise
        existing = (
            await db.execute(select(Job).where(Job.idempotency_key == idempotency_key))
        ).scalar_one_or_none()
        if existing is None or existing.request_hash != fingerprint:
            raise AppException(409, "Conflicting job submission", "CONFLICT") from None
        return existing, False
    return job, True


async def get_job(db: AsyncSession, job_id: str) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise NotFoundException("Job not found")
    return job


class JobRunner:
    def __init__(self, sessions: async_sessionmaker, concurrency: int = 2):
        self.sessions = sessions
        self.concurrency = concurrency
        self.handlers: dict[str, Handler] = {}
        self.failure_handlers: dict[str, FailureHandler] = {}
        self.tasks: list[asyncio.Task] = []
        self.stopping = False

    def register(self, kind: str, handler: Handler, failure: FailureHandler | None = None):
        self.handlers[kind] = handler
        if failure:
            self.failure_handlers[kind] = failure

    async def start(self):
        self.stopping = False
        await self.recover_interrupted()
        self.tasks = [
            asyncio.create_task(self._loop(), name=f"figure-job-{i}")
            for i in range(self.concurrency)
        ]

    async def stop(self):
        self.stopping = True
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

    async def recover_interrupted(self):
        async with self.sessions() as db:
            jobs = list((await db.scalars(select(Job).where(Job.status == "running"))).all())
            for job in jobs:
                await self._fail(
                    db,
                    job,
                    "interrupted",
                    "Application stopped during this attempt. Provider outcome may be unknown; "
                    "check usage before retrying.",
                )
            legacy_message = (
                "This unfinished record predates durable jobs. No request was resubmitted; "
                "check provider usage before starting another generation."
            )
            await db.execute(
                update(Image)
                .where(
                    Image.job_id.is_(None),
                    Image.generation_status.in_(["pending", "generating"]),
                )
                .values(generation_status="interrupted", generation_error=legacy_message)
            )
            await db.execute(
                update(Document)
                .where(
                    Document.job_id.is_(None),
                    Document.parse_status.in_(["pending", "parsing"]),
                )
                .values(
                    parse_status="interrupted",
                    parse_error="Document parsing did not finish before the upgrade. Re-upload it.",
                )
            )
            await db.commit()

    async def claim(self) -> Job | None:
        async with self.sessions() as db:
            candidate = (
                await db.scalars(
                    select(Job.id)
                    .where(Job.status == "queued")
                    .order_by(Job.created_at, Job.id)
                    .limit(1)
                )
            ).first()
            if not candidate:
                return None
            result = await db.execute(
                update(Job)
                .where(Job.id == candidate, Job.status == "queued")
                .values(status="running", stage="processing", started_at=now())
            )
            await db.commit()
            if result.rowcount != 1:
                return None
            return await db.get(Job, candidate)

    async def _fail(self, db: AsyncSession, job: Job, status: str, error: str):
        await db.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(status=status, stage=status, error=error, finished_at=now())
        )
        if job.kind in self.failure_handlers:
            await self.failure_handlers[job.kind](job, db, status, error)

    async def execute(self, job: Job):
        try:
            async with self.sessions() as db:
                handler = self.handlers.get(job.kind)
                if handler is None:
                    raise ValueError("Unsupported job kind")
                result = await handler(job, db)
                await db.execute(
                    update(Job)
                    .where(Job.id == job.id, Job.status == "running")
                    .values(
                        status="succeeded",
                        stage="completed",
                        result=result,
                        finished_at=now(),
                        error=None,
                    )
                )
                await db.commit()
        except asyncio.CancelledError:
            async with self.sessions() as db:
                await self._fail(
                    db,
                    job,
                    "interrupted",
                    "Application stopped during this attempt. Provider outcome may be unknown; "
                    "check usage before retrying.",
                )
                await db.commit()
            raise
        except Exception as exc:
            logger.warning("Job %s failed (%s)", job.id, type(exc).__name__)
            async with self.sessions() as db:
                await self._fail(db, job, "failed", public_error(exc))
                await db.commit()

    async def _loop(self):
        while not self.stopping:
            try:
                job = await self.claim()
                if job:
                    await self.execute(job)
                else:
                    await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Job polling failed (%s)", type(exc).__name__)
                await asyncio.sleep(1)
