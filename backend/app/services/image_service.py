"""OpenAI image generation and editing service."""

from __future__ import annotations

import base64
import logging
import math
import time
from typing import Any

from app.config import get_settings
from app.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)


class ImageService:
    """Integration with OpenAI Image API for generation and image-to-image edits."""

    RESOLUTION_AREA_MAP: dict[str, int] = {
        "1K": 1024 * 1024,
        "2K": 2048 * 2048,
        "4K": 8_294_400,
    }

    ASPECT_RATIO_MAP: dict[str, tuple[int, int]] = {
        "1:1": (1, 1),
        "16:9": (16, 9),
        "9:16": (9, 16),
        "4:3": (4, 3),
        "3:4": (3, 4),
        "3:2": (3, 2),
        "2:3": (2, 3),
        "21:9": (21, 9),
        "9:21": (9, 21),
        "1:2": (1, 2),
    }

    TIMEOUT_MAP: dict[str, int] = {
        "1K": 360,
        "2K": 600,
        "4K": 1200,
    }

    MAX_EDGE_PX = 3840
    MAX_TOTAL_PIXELS = 8_294_400
    MAX_ASPECT_RATIO = 3.0
    SIZE_MULTIPLE = 16

    def __init__(self, api_key: str | None = None, api_base_url: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.api_base = (api_base_url or settings.OPENAI_API_BASE).rstrip("/")
        self.model = settings.OPENAI_IMAGE_MODEL
        self.quality = settings.OPENAI_IMAGE_QUALITY

        if not self.api_key:
            raise ExternalAPIException(
                "OpenAI",
                "OPENAI_API_KEY is not configured. Set it in your system environment, "
                "a local .env file, or backend/app/config.py.",
            )

    def generate_image(
        self,
        prompt: str,
        resolution: str = "2K",
        aspect_ratio: str = "16:9",
        reference_image_bytes: bytes | None = None,
        edit_instruction: str | None = None,
    ) -> dict:
        """Generate or edit an image via OpenAI synchronously."""
        width, height = self._calculate_dimensions(resolution, aspect_ratio)
        size_str = f"{width}x{height}"
        timeout = self.TIMEOUT_MAP.get(resolution, 600)
        start_time = time.monotonic()

        try:
            if reference_image_bytes:
                result = self._edit_image(
                    prompt=prompt,
                    reference_image_bytes=reference_image_bytes,
                    edit_instruction=edit_instruction,
                    size=size_str,
                    timeout=timeout,
                )
            else:
                result = self._generate_image(
                    prompt=prompt,
                    size=size_str,
                    timeout=timeout,
                )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("OpenAI image API failed after %d ms: %s", duration_ms, exc)
            raise ExternalAPIException("OpenAI", f"Image request failed: {exc}") from exc

        duration_ms = int((time.monotonic() - start_time) * 1000)
        image_base64 = self._extract_image_base64(result)
        if not image_base64:
            raise ExternalAPIException("OpenAI", "Empty base64 image data in response")

        logger.info(
            "OpenAI image generated in %d ms: %dx%d (resolution=%s, aspect=%s)",
            duration_ms,
            width,
            height,
            resolution,
            aspect_ratio,
        )
        return {
            "image_base64": image_base64,
            "width": width,
            "height": height,
            "duration_ms": duration_ms,
        }

    def _generate_image(self, prompt: str, size: str, timeout: int) -> Any:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(api_key=self.api_key, base_url=self.api_base, timeout=timeout)
        return client.images.generate(
            model=self.model,
            prompt=prompt,
            size=size,
            quality=self.quality,
            n=1,
        )

    def _edit_image(
        self,
        prompt: str,
        reference_image_bytes: bytes | None,
        edit_instruction: str | None,
        size: str,
        timeout: int,
    ) -> Any:
        if not reference_image_bytes:
            raise ValueError("reference_image_bytes is required for image editing")

        from openai import OpenAI  # noqa: PLC0415

        combined_prompt = prompt
        if edit_instruction and edit_instruction.strip():
            combined_prompt = (
                f"{edit_instruction.strip()}\n\nOriginal prompt context:\n{prompt}"
            ).strip()

        client = OpenAI(api_key=self.api_key, base_url=self.api_base, timeout=timeout)
        return client.images.edit(
            model=self.model,
            image=("reference.png", reference_image_bytes, "image/png"),
            prompt=combined_prompt,
            size=size,
            quality=self.quality,
            n=1,
        )

    @classmethod
    def _calculate_dimensions(cls, resolution: str, aspect_ratio: str) -> tuple[int, int]:
        """Calculate OpenAI-compatible dimensions for the selected tier and aspect."""
        target_area = cls.RESOLUTION_AREA_MAP.get(resolution, cls.RESOLUTION_AREA_MAP["2K"])
        rw, rh = cls.ASPECT_RATIO_MAP.get(aspect_ratio, (16, 9))
        ratio = rw / rh

        if ratio > cls.MAX_ASPECT_RATIO:
            ratio = cls.MAX_ASPECT_RATIO
        elif ratio < 1 / cls.MAX_ASPECT_RATIO:
            ratio = 1 / cls.MAX_ASPECT_RATIO

        target_area = min(target_area, cls.MAX_TOTAL_PIXELS)
        width = math.sqrt(target_area * ratio)
        height = width / ratio

        max_edge = max(width, height)
        if max_edge > cls.MAX_EDGE_PX:
            scale = cls.MAX_EDGE_PX / max_edge
            width *= scale
            height *= scale

        if width * height > cls.MAX_TOTAL_PIXELS:
            scale = math.sqrt(cls.MAX_TOTAL_PIXELS / (width * height))
            width *= scale
            height *= scale

        width = cls._floor_to_multiple(width, cls.SIZE_MULTIPLE)
        height = cls._floor_to_multiple(height, cls.SIZE_MULTIPLE)
        return width, height

    @staticmethod
    def _floor_to_multiple(value: float, multiple: int) -> int:
        return max(multiple, int(value // multiple) * multiple)

    @staticmethod
    def _extract_image_base64(result: Any) -> str:
        data = result.get("data", []) if isinstance(result, dict) else getattr(
            result, "data", []
        )
        if not data:
            raise ExternalAPIException("OpenAI", "No image data returned in response")

        first = data[0]
        if isinstance(first, dict):
            return str(first.get("b64_json") or "")
        return str(getattr(first, "b64_json", "") or "")

    @staticmethod
    def image_bytes_from_base64(b64_string: str) -> bytes:
        """Decode a base64-encoded image string to raw bytes."""
        return base64.b64decode(b64_string)

    @staticmethod
    def image_size_bytes(b64_string: str) -> int:
        """Estimate the decoded byte size of a base64 image string."""
        padding = b64_string.count("=")
        return (len(b64_string) * 3) // 4 - padding
