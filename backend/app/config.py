"""Application settings — personal-use local version."""

from functools import lru_cache
from os import PathLike
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import DotEnvSettingsSource

# Project root: backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_ROOT.parent


ApiKeySource = Literal["environment", "backend_dotenv", "root_dotenv", "code_default", "missing"]


class _CredentialDotEnvSource(DotEnvSettingsSource):
    key_source: ApiKeySource = "missing"

    def _read_env_file(self, file_path: Path) -> dict[str, str | None]:
        values = dict(super()._read_env_file(file_path))
        key_name = f"{self.env_prefix}OPENAI_API_KEY"
        if not self.case_sensitive:
            key_name = key_name.lower()
        key = values.get(key_name)
        if not key or not key.strip():
            values.pop(key_name, None)
        else:
            values[key_name] = key.strip()
            files = self.env_file
            if isinstance(files, (str, PathLike)):
                files = [files]
            root_file = file_path.resolve() == (_PROJECT_ROOT / ".env").resolve()
            if files and len(files) > 1:
                root_file = root_file or file_path == Path(files[0]).expanduser()
            self.key_source = "root_dotenv" if root_file else "backend_dotenv"
        return values


def _credential_source(source: PydanticBaseSettingsSource, label: ApiKeySource):
    def values_with_source() -> dict:
        values = source()
        # Provenance is computed by the loader, never accepted from .env or callers.
        values.pop("api_key_source", None)
        key = values.get("OPENAI_API_KEY")
        if isinstance(key, str) and key.strip():
            values["OPENAI_API_KEY"] = key.strip()
            values["api_key_source"] = (
                source.key_source if isinstance(source, _CredentialDotEnvSource) else label
            )
        elif key is None or isinstance(key, str):
            values.pop("OPENAI_API_KEY", None)
        return values

    return values_with_source


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
    OPENAI_API_KEY: str = Field(default="", repr=False, exclude=True)
    api_key_source: ApiKeySource = Field(default="code_default", exclude=True)
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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: DotEnvSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        dotenv = _CredentialDotEnvSource(
            settings_cls,
            env_file=dotenv_settings.env_file,
            env_file_encoding=dotenv_settings.env_file_encoding,
            case_sensitive=dotenv_settings.case_sensitive,
            env_prefix=dotenv_settings.env_prefix,
            env_ignore_empty=True,
            env_parse_none_str=dotenv_settings.env_parse_none_str,
            env_parse_enums=dotenv_settings.env_parse_enums,
        )
        return (
            _credential_source(init_settings, "code_default"),
            _credential_source(env_settings, "environment"),
            _credential_source(dotenv, "backend_dotenv"),
            _credential_source(file_secret_settings, "code_default"),
        )

    @field_validator("OPENAI_API_KEY")
    @classmethod
    def _normalize_api_key(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _missing_api_key_source(self) -> Self:
        if not self.OPENAI_API_KEY:
            self.api_key_source = "missing"
        return self

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
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
