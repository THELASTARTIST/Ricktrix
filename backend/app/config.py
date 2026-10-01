"""Configuration, loaded from the environment with a small .env reader.

Deliberately dependency-free: python-dotenv is one more thing that can fail to
install on a fresh machine, and reading KEY=value lines is not worth the risk.
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_ROOT / ".env"
ARTIFACTS = BACKEND_ROOT / "ml" / "artifacts"


def load_env(path: Path = ENV_PATH) -> None:
    """Populate os.environ from a .env file. Existing variables win."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        value = value.strip().strip("'\"")
        # setdefault so a real environment variable overrides the file.
        os.environ.setdefault(key, value)


load_env()


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def supabase_url() -> str:
    return _get("SUPABASE_URL")


def supabase_anon_key() -> str:
    return _get("SUPABASE_ANON_KEY")


def supabase_service_key() -> str:
    return _get("SUPABASE_SERVICE_ROLE_KEY")


def using_supabase() -> bool:
    """True only when there is enough configuration to reach a real database."""
    return bool(supabase_url() and supabase_anon_key())


def cors_origins() -> list[str]:
    """Extra origins allowed to call the API, or [] for same-origin only.

    Empty is the default and the right one: the FastAPI process serves the API
    and the static site from the same origin, so no cross-origin request is
    ever made and there is nothing to allow.

    It is deliberately not "*". Starlette would send
    `Access-Control-Allow-Origin: *` alongside
    `Access-Control-Allow-Credentials: true`, and browsers reject that pairing
    outright -- so "*" does not even work for the authenticated endpoints it
    appears to permit. Set an explicit comma-separated list of origins if you
    ever host the site somewhere other than this process.
    """
    raw = _get("CORS_ORIGINS")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def admin_emails() -> set[str]:
    """Emails allowed to read the moderation queue.

    Unset means nobody is an admin, which is the safe default: a missing env
    var must never expose the review queue.
    """
    return {
        email.strip().lower()
        for email in _get("ADMIN_EMAILS").split(",")
        if email.strip()
    }


def model_dir() -> Path:
    return ARTIFACTS
