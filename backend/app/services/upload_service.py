"""Bounded uploads and decoded image validation before any provider request."""

import io
import warnings
from pathlib import PurePosixPath

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import get_settings
from app.core.exceptions import AppException, FileValidationException

MAX_IMAGE_PIXELS = 33_177_600


async def read_upload(file: UploadFile, max_bytes: int | None = None) -> bytes:
    limit = max_bytes or get_settings().MAX_UPLOAD_SIZE_MB * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(min(1024 * 1024, limit + 1 - total)):
        total += len(chunk)
        if total > limit:
            raise AppException(
                413, "Uploaded file exceeds the configured size limit", "UPLOAD_TOO_LARGE"
            )
        chunks.append(chunk)
    if not total:
        raise FileValidationException("Uploaded file is empty")
    return b"".join(chunks)


def display_filename(filename: str | None) -> str:
    name = PurePosixPath((filename or "unnamed").replace("\\", "/")).name
    return "".join(character for character in name if character.isprintable())[:500] or "unnamed"


def inspect_image(data: bytes) -> dict:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise FileValidationException("Only PNG, JPEG, and WebP images are supported")
                if getattr(image, "n_frames", 1) != 1:
                    raise FileValidationException("Animated reference images are not supported")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise FileValidationException("Image dimensions exceed the decoded pixel limit")
                image.load()
                return {
                    "width": image.width,
                    "height": image.height,
                    "format": image.format,
                    "mime_type": Image.MIME[image.format],
                    "has_alpha": "A" in image.getbands() or "transparency" in image.info,
                }
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise FileValidationException("Invalid or excessively large image") from exc


def validate_mask(reference: bytes, mask: bytes) -> None:
    reference_info, mask_info = inspect_image(reference), inspect_image(mask)
    if mask_info["format"] != "PNG" or not mask_info["has_alpha"]:
        raise FileValidationException("Mask must be a PNG with an alpha channel")
    if (reference_info["width"], reference_info["height"]) != (
        mask_info["width"],
        mask_info["height"],
    ):
        raise FileValidationException("Mask dimensions must match the reference image")
    with Image.open(io.BytesIO(mask)) as image:
        if image.convert("RGBA").getchannel("A").getextrema()[0] == 255:
            raise FileValidationException("Mask has no transparent edit region")


def reference_png(data: bytes) -> bytes:
    inspect_image(data)
    with Image.open(io.BytesIO(data)) as image:
        output = io.BytesIO()
        image.convert("RGBA").save(output, format="PNG")
    result = output.getvalue()
    if len(result) >= 50 * 1024 * 1024:
        raise FileValidationException("Decoded PNG reference exceeds the provider upload limit")
    return result
