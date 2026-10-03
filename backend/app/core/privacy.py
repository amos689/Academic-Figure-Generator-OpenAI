"""Public diagnostics never contain provider bodies, prompts, or credentials."""

import logging
import re

from app.config import get_settings


def redact_secrets(value: str) -> str:
    key = get_settings().OPENAI_API_KEY
    if key:
        value = value.replace(key, "[REDACTED]")
    value = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [REDACTED]", value)
    return re.sub(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{8,}", "[REDACTED]", value)


def public_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return "OpenAI access was denied. Check the configured key and model permissions."
    if status == 429:
        return "OpenAI rate or quota limit reached. Check your account before retrying."
    if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
        return "The provider timed out. The result may be unknown; check usage before retrying."
    if status is not None:
        return f"Provider request failed (HTTP {status}). Check model and request settings."
    return f"Operation failed ({type(exc).__name__}). Check the input and local configuration."


class SecretRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(record.getMessage())
        record.args = ()
        # Provider tracebacks can embed an echoed request body or authorization header.
        if record.exc_info:
            record.msg += f" ({record.exc_info[0].__name__})"
            record.exc_info = None
            record.exc_text = None
        return True


def configure_private_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(item, SecretRedactingFilter) for item in handler.filters):
                handler.addFilter(SecretRedactingFilter())
