from __future__ import annotations

import json

import pytest
from pydantic import Field, ValidationError

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _clear_openai_env(monkeypatch):
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_TEXT_MODEL",
        "OPENAI_TEXT_REASONING_EFFORT",
        "OPENAI_TEXT_MAX_OUTPUT_TOKENS",
        "OPENAI_IMAGE_MODEL",
        "OPENAI_IMAGE_QUALITY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_environment_variable_overrides_code_default(monkeypatch):
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "env-text-model")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.OPENAI_API_KEY == "env-key"
    assert settings.OPENAI_TEXT_MODEL == "env-text-model"
    assert settings.OPENAI_IMAGE_MODEL == "gpt-image-2.5-sunburst"


def test_environment_variable_overrides_local_env_file(monkeypatch, tmp_path):
    _clear_openai_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=dotenv-key\nOPENAI_TEXT_MODEL=dotenv-text-model\n"
        "OPENAI_IMAGE_MODEL=dotenv-image-model\nOPENAI_IMAGE_QUALITY=high\n"
        "OPENAI_TEXT_REASONING_EFFORT=medium\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "env-image-model")
    monkeypatch.setenv("OPENAI_IMAGE_QUALITY", "xhigh")
    monkeypatch.setenv("OPENAI_TEXT_REASONING_EFFORT", "high")

    settings = Settings(_env_file=str(env_file))

    assert settings.OPENAI_API_KEY == "env-key"
    assert settings.OPENAI_TEXT_MODEL == "dotenv-text-model"
    assert settings.OPENAI_IMAGE_MODEL == "env-image-model"
    assert settings.OPENAI_IMAGE_QUALITY == "xhigh"
    assert settings.OPENAI_TEXT_REASONING_EFFORT == "high"


def test_local_env_file_overrides_code_default(monkeypatch, tmp_path):
    _clear_openai_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=dotenv-key\nOPENAI_IMAGE_MODEL=custom-image-model\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=str(env_file))

    assert settings.OPENAI_API_KEY == "dotenv-key"
    assert settings.OPENAI_IMAGE_MODEL == "custom-image-model"
    assert settings.OPENAI_TEXT_MODEL == "gpt-6-astra"


@pytest.mark.parametrize(
    "environment,backend,root,expected,source",
    [
        ("env-secret", "backend-secret", "root-secret", "env-secret", "environment"),
        (None, "backend-secret", "root-secret", "backend-secret", "backend_dotenv"),
        (None, None, "root-secret", "root-secret", "root_dotenv"),
        ("", "backend-secret", "root-secret", "backend-secret", "backend_dotenv"),
        ("  \t ", "backend-secret", "root-secret", "backend-secret", "backend_dotenv"),
        (None, "", "root-secret", "root-secret", "root_dotenv"),
        (None, "  \t ", "root-secret", "root-secret", "root_dotenv"),
        ("", "", "", "", "missing"),
        (None, None, None, "", "missing"),
        ("same-secret", "same-secret", "same-secret", "same-secret", "environment"),
        (None, "same-secret", "same-secret", "same-secret", "backend_dotenv"),
    ],
)
def test_key_source_and_blank_fallback(
    monkeypatch, tmp_path, environment, backend, root, expected, source
):
    files = [tmp_path / "root.env", tmp_path / "backend.env"]
    for path, value in zip(files, (root, backend), strict=True):
        path.write_text(
            "" if value is None else f"OPENAI_API_KEY={json.dumps(value)}\n", encoding="utf-8"
        )
    if environment is not None:
        monkeypatch.setenv("OPENAI_API_KEY", environment)
    settings = Settings(_env_file=files)
    assert settings.OPENAI_API_KEY == expected
    assert settings.api_key_source == source


def test_environment_backend_root_default_precedence_for_all_effective_fields(
    monkeypatch, tmp_path
):
    root, backend = tmp_path / "root.env", tmp_path / "backend.env"
    root.write_text(
        "OPENAI_TEXT_MODEL=root-text\nOPENAI_IMAGE_MODEL=root-image\n"
        "OPENAI_IMAGE_QUALITY=high\nOPENAI_TEXT_MAX_OUTPUT_TOKENS=4096\n",
        encoding="utf-8",
    )
    backend.write_text(
        "OPENAI_TEXT_MODEL=backend-text\nOPENAI_IMAGE_MODEL=backend-image\nOPENAI_IMAGE_QUALITY=\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "env-text")
    monkeypatch.setenv("OPENAI_TEXT_REASONING_EFFORT", "")
    settings = Settings(_env_file=(root, backend))
    assert settings.OPENAI_TEXT_MODEL == "env-text"
    assert settings.OPENAI_IMAGE_MODEL == "backend-image"
    assert settings.OPENAI_IMAGE_QUALITY == "high"
    assert settings.OPENAI_TEXT_MAX_OUTPUT_TOKENS == 4096
    assert settings.OPENAI_TEXT_REASONING_EFFORT == "max"


def test_code_default_key_and_constructor_override_have_code_source(monkeypatch):
    class Defaults(Settings):
        OPENAI_API_KEY: str = Field(default="default-secret", repr=False, exclude=True)

    assert Defaults(_env_file=None).api_key_source == "code_default"
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")
    assert Defaults(_env_file=None).api_key_source == "environment"
    initialized = Settings(_env_file=None, OPENAI_API_KEY="explicit-secret")
    assert initialized.OPENAI_API_KEY == "explicit-secret"
    assert initialized.api_key_source == "code_default"


def test_source_is_snapshot_and_cannot_be_forged(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=file-secret\napi_key_source=environment\n", encoding="utf-8")
    monkeypatch.setenv("API_KEY_SOURCE", "environment")
    settings = Settings(_env_file=path, api_key_source="environment")
    assert settings.api_key_source == "backend_dotenv"
    monkeypatch.setenv("OPENAI_API_KEY", "new-env-secret")
    path.write_text("OPENAI_API_KEY=new-file-secret\n", encoding="utf-8")
    assert settings.api_key_source == "backend_dotenv"
    assert settings.OPENAI_API_KEY == "file-secret"


def test_case_insensitive_key_and_secret_not_serialized(monkeypatch):
    monkeypatch.setenv("openai_api_key", "  private-secret  ")
    settings = Settings(_env_file=None)
    assert settings.OPENAI_API_KEY == "private-secret"
    assert settings.api_key_source == "environment"
    assert "OPENAI_API_KEY" not in settings.model_dump()
    assert "private-secret" not in settings.model_dump_json()
    assert "private-secret" not in repr(settings)


def test_bare_backend_key_does_not_override_root(tmp_path):
    root, backend = tmp_path / "root.env", tmp_path / "backend.env"
    root.write_text("OPENAI_API_KEY=root-secret\n", encoding="utf-8")
    backend.write_text("OPENAI_API_KEY\n", encoding="utf-8")
    settings = Settings(_env_file=(root, backend))
    assert settings.OPENAI_API_KEY == "root-secret"
    assert settings.api_key_source == "root_dotenv"


def test_concurrency_and_allowed_hosts_preserved(monkeypatch):
    monkeypatch.setenv("MAX_CONCURRENT_JOBS", "4")
    monkeypatch.setenv("ALLOWED_HOSTS", '["localhost","example.test"]')
    settings = Settings(_env_file=None)
    assert settings.MAX_CONCURRENT_JOBS == 4
    assert settings.ALLOWED_HOSTS == ["localhost", "example.test"]
    monkeypatch.delenv("MAX_CONCURRENT_JOBS")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, MAX_CONCURRENT_JOBS=9)


@pytest.mark.parametrize(
    "base",
    [
        "https://user:secret@api.example.test/v1",
        "https://api.example.test/v1?key=secret",
        "https://api.example.test/v1#secret",
        "file:///tmp/secret",
    ],
)
def test_api_base_cannot_contain_credentials(base):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, OPENAI_API_BASE=base)


@pytest.mark.parametrize("prefix,expected", [("", "/api/v1"), ("v2/", "/v2"), ("/", "/api/v1")])
def test_api_prefix_normalization_is_preserved(prefix, expected):
    assert Settings(_env_file=None, API_V1_PREFIX=prefix).API_V1_PREFIX == expected
