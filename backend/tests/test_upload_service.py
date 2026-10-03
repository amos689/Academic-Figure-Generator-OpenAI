import io

import httpx
import pytest
from fastapi import FastAPI, Request, UploadFile
from PIL import Image

from app.core.exceptions import AppException, FileValidationException
from app.core.upload_limit import UploadLimitMiddleware
from app.services.upload_service import (
    display_filename,
    inspect_image,
    read_upload,
    reference_png,
    validate_mask,
)


def image_bytes(size=(32, 32), mode="RGB", format="PNG", color=None):
    output = io.BytesIO()
    Image.new(mode, size, color).save(output, format=format)
    return output.getvalue()


async def test_upload_limits_and_empty_files():
    for contents, code in [(b"", 422), (b"12345", 413)]:
        with pytest.raises(AppException) as error:
            await read_upload(UploadFile(io.BytesIO(contents)), max_bytes=4)
        assert error.value.status_code == code
    assert await read_upload(UploadFile(io.BytesIO(b"1234")), max_bytes=4) == b"1234"
    assert display_filename("../../private\\paper.txt") == "paper.txt"


def test_detect_actual_format_and_reject_corrupt_image():
    assert inspect_image(image_bytes(format="JPEG"))["mime_type"] == "image/jpeg"
    assert inspect_image(reference_png(image_bytes(format="JPEG")))["format"] == "PNG"
    with pytest.raises(FileValidationException):
        inspect_image(b"not an image")
    with pytest.raises(FileValidationException):
        inspect_image(image_bytes()[:25])


def test_masks_require_dimensions_alpha_and_edit_region():
    reference = image_bytes()
    validate_mask(reference, image_bytes(mode="RGBA"))
    for mask in [
        image_bytes(),
        image_bytes(mode="RGBA", size=(16, 16)),
        image_bytes(mode="RGBA", color=(0, 0, 0, 255)),
    ]:
        with pytest.raises(FileValidationException):
            validate_mask(reference, mask)


async def test_http_body_limit_includes_chunked_uploads():
    app = FastAPI()
    app.add_middleware(UploadLimitMiddleware, max_bytes=4)

    @app.post("/upload")
    async def upload(request: Request):
        return {"size": len(await request.body())}

    async def chunks():
        yield b"12"
        yield b"345"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://localhost"
    ) as client:
        assert (await client.post("/upload", content=b"12345")).status_code == 413
        assert (await client.post("/upload", content=chunks())).status_code == 413
        assert (await client.post("/upload", content=b"1234")).json() == {"size": 4}
