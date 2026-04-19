"""Configuration module — reads env vars for Gemini + OCR settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    gemini_endpoint: str
    tesseract_cmd: str | None
    poppler_path: str | None
    max_upload_bytes: int
    allowed_mime_types: tuple[str, ...]
    cors_origins: tuple[str, ...]


def _get_cors_origins() -> tuple[str, ...]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return tuple(o.strip() for o in raw.split(",") if o.strip())


settings = Settings(
    gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
    gemini_model=os.getenv("GEMINI_MODEL", "gemma-3-27b-it"),
    gemini_endpoint=os.getenv(
        "GEMINI_ENDPOINT",
        "https://generativelanguage.googleapis.com/v1beta/models",
    ),
    tesseract_cmd=os.getenv("TESSERACT_CMD") or None,
    poppler_path=os.getenv("POPPLER_PATH") or None,
    max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
    allowed_mime_types=(
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
    ),
    cors_origins=_get_cors_origins(),
)
