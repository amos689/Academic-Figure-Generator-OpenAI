import pytest

from app.services.process_service import run_offline, stop_offline_workers


async def test_process_worker_parses_document_and_shuts_down():
    try:
        result = await run_offline("parse_document", b"# Methods\nOriginal fixture.", "txt")
        assert result["sections"][0]["content"] == "Original fixture."
        with pytest.raises(ValueError, match="Unknown"):
            await run_offline("not-an-operation")
    finally:
        await stop_offline_workers()
