"""Application settings — personal-use local version."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_ROOT.parent


class Settings(BaseSettings):
    # App
    APP_NAME: str = "academic-figure-generator"
    DEBUG: bool = True
    SECRET_KEY: str = "local-dev-key"
    API_V1_PREFIX: str = "/api/v1"

    # SQLite
    DATABASE_PATH: str = str(_BACKEND_ROOT / "data" / "app.db")

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        return f"sqlite+aiosqlite:///{self.DATABASE_PATH}"

    # Data directory (uploads, figures)
    DATA_DIR: str = str(_BACKEND_ROOT / "data")

    # OpenAI API (system env -> .env -> these code defaults)
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_TEXT_MODEL: str = "gpt-6-astra"
    OPENAI_TEXT_REASONING_EFFORT: str = "max"
    # Includes both reasoning tokens and the final structured prompts.
    OPENAI_TEXT_MAX_OUTPUT_TOKENS: int = 32768
    OPENAI_IMAGE_MODEL: str = "gpt-image-2.5-sunburst"
    OPENAI_IMAGE_QUALITY: str = "max"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "[::1]", "testserver"]

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_CONCURRENT_JOBS: int = Field(default=2, ge=1, le=8)

    @field_validator("API_V1_PREFIX")
    @classmethod
    def _normalize_api_prefix(cls, value: str) -> str:
        prefix = (value or "").strip()
        if not prefix:
            return "/api/v1"
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        prefix = prefix.rstrip("/")
        return prefix or "/api/v1"

    @field_validator("OPENAI_API_BASE")
    @classmethod
    def _normalize_openai_api_base(cls, value: str) -> str:
        value = (value or "https://api.openai.com/v1").rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("OPENAI_API_BASE must be an HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("OPENAI_API_BASE must not contain credentials, query, or fragment")
        return value

    model_config = SettingsConfigDict(
        env_file=(str(_PROJECT_ROOT / ".env"), str(_BACKEND_ROOT / ".env")),
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
