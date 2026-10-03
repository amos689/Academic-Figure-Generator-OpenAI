"""Isolate PyMuPDF work: its parser and font/rendering APIs are not thread-safe."""

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from app.config import get_settings

_pool: ProcessPoolExecutor | None = None


def _dispatch(operation: str, arguments: tuple, keywords: dict):
    if operation == "parse_document":
        from app.services.document_service import DocumentService

        return DocumentService().parse(*arguments, **keywords)
    if operation == "export_figure":
        from app.services.vector_export_service import VectorExportService

        return VectorExportService().render(*arguments, **keywords)
    raise ValueError("Unknown offline processing operation")


async def run_offline(operation: str, *arguments, **keywords):
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(
            max_workers=get_settings().MAX_CONCURRENT_JOBS,
            mp_context=multiprocessing.get_context("spawn"),
        )
    return await asyncio.get_running_loop().run_in_executor(
        _pool, _dispatch, operation, arguments, keywords
    )


async def stop_offline_workers():
    global _pool
    if _pool is not None:
        pool, _pool = _pool, None
        await asyncio.to_thread(pool.shutdown, wait=True, cancel_futures=True)
