"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    app_name: str = "数据结构实验自测平台"
    api_prefix: str = "/api"

    database_url: str = "sqlite:///./data/code_judge.db"

    # Runner internal service
    runner_url: str = "http://127.0.0.1:8100"

    # Admin bootstrap
    admin_username: str = "admin"
    admin_password: str = "admin123456"  # change in production via .env

    # Security
    secret_key: str = ""
    cookie_secure: bool = False
    cookie_samesite: str = "strict"
    cookie_max_age_seconds: int = 12 * 60 * 60
    allowed_origin: str = ""  # e.g. https://test.example.com
    trust_proxy_headers: bool = False

    # Concurrency and rate limiting
    judge_max_concurrency: int = 4
    judge_queue_size: int = 50
    judge_rate_per_minute: int = 10
    admin_verify_max_concurrency: int = 2
    admin_verify_rate_per_minute: int = 20

    # Limits
    max_source_bytes: int = 64 * 1024
    max_custom_input_bytes: int = 1024 * 1024
    max_test_cases: int = 20
    max_case_bytes: int = 1024 * 1024

    # Frontend static path
    frontend_dist: str = "frontend/dist"

    def finalize_secret(self) -> None:
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)


def _load_from_env() -> Settings:
    s = Settings(
        app_name=os.getenv("APP_NAME", Settings.app_name),
        api_prefix=os.getenv("API_PREFIX", Settings.api_prefix),
        database_url=os.getenv("DATABASE_URL", Settings.database_url),
        runner_url=os.getenv("RUNNER_URL", Settings.runner_url),
        admin_username=os.getenv("ADMIN_USERNAME", Settings.admin_username),
        admin_password=os.getenv("ADMIN_PASSWORD", Settings.admin_password),
        secret_key=os.getenv("SECRET_KEY", ""),
        cookie_secure=_bool(os.getenv("COOKIE_SECURE"), False),
        cookie_samesite=os.getenv("COOKIE_SAMESITE", "strict"),
        cookie_max_age_seconds=_int(os.getenv("COOKIE_MAX_AGE_SECONDS"), 12 * 60 * 60),
        allowed_origin=os.getenv("ALLOWED_ORIGIN", "").rstrip("/"),
        trust_proxy_headers=_bool(os.getenv("TRUST_PROXY_HEADERS"), False),
        judge_max_concurrency=_int(os.getenv("JUDGE_MAX_CONCURRENCY"), 4),
        judge_queue_size=_int(os.getenv("JUDGE_QUEUE_SIZE"), 50),
        judge_rate_per_minute=_int(os.getenv("JUDGE_RATE_PER_MINUTE"), 10),
        admin_verify_max_concurrency=_int(os.getenv("ADMIN_VERIFY_MAX_CONCURRENCY"), 2),
        admin_verify_rate_per_minute=_int(os.getenv("ADMIN_VERIFY_RATE_PER_MINUTE"), 20),
        max_source_bytes=_int(os.getenv("MAX_SOURCE_BYTES"), 64 * 1024),
        max_custom_input_bytes=_int(os.getenv("MAX_CUSTOM_INPUT_BYTES"), 1024 * 1024),
        max_test_cases=_int(os.getenv("MAX_TEST_CASES"), 20),
        max_case_bytes=_int(os.getenv("MAX_CASE_BYTES"), 1024 * 1024),
        frontend_dist=os.getenv("FRONTEND_DIST", Settings.frontend_dist),
    )
    s.finalize_secret()
    return s


_settings_cache: Settings | None = None


def get_settings() -> Settings:
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = _load_from_env()
    return _settings_cache


def ensure_data_dir(settings: Settings | None = None) -> None:
    """Create the data directory if it does not exist."""
    settings = settings or get_settings()
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.removeprefix("sqlite:///")
        if db_path and db_path != ":memory:" and not Path(db_path).is_absolute():
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
