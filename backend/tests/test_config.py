from __future__ import annotations

from app.config import Settings, get_settings


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
