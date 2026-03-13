"""
config.py – centralised configuration loaded from environment variables.
All modules import settings from here instead of directly from os.environ.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # ── Terabox ──────────────────────────────────────────────────────────────
    TERABOX_EMAIL: str = os.getenv("TERABOX_EMAIL", "")
    TERABOX_PASSWORD: str = os.getenv("TERABOX_PASSWORD", "")
    TERABOX_COOKIE_FILE: str = str(BASE_DIR / "database" / "terabox_cookies.json")

    TERABOX_VALID_DOMAINS = {
        "terabox.com",
        "1024terabox.com",
        "teraboxapp.com",
        "www.terabox.com",
        "www.1024terabox.com",
        "www.teraboxapp.com",
    }

    # ── Telegram ─────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # ── Worker ────────────────────────────────────────────────────────────────
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "3"))
    JOB_TIMEOUT: int = int(os.getenv("JOB_TIMEOUT", "300"))
    RETRY_COUNT: int = int(os.getenv("RETRY_COUNT", "3"))
    RETRY_DELAY: int = int(os.getenv("RETRY_DELAY", "10"))

    # ── Dashboard ─────────────────────────────────────────────────────────────
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8080"))
    DASHBOARD_ENABLED: bool = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"

    # ── Processing ────────────────────────────────────────────────────────────
    ENABLE_AUTO_CATEGORIZE: bool = (
        os.getenv("ENABLE_AUTO_CATEGORIZE", "true").lower() == "true"
    )
    DUPLICATE_ACTION: str = os.getenv("DUPLICATE_ACTION", "skip")  # skip | rename

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "bot.log"))

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'database' / 'db.sqlite'}"
    )

    # ── Auto-categorisation keyword map ──────────────────────────────────────
    CATEGORY_MAP: dict = {
        "Movies": ["movie", "film", "cinema", "mkv", "mp4", "avi", "bluray", "bdrip"],
        "Anime": ["anime", "episode", "ova", "ona", "sub", "dub", "webrip"],
        "Software": ["software", "app", "setup", "installer", "crack", "patch", "iso"],
        "Apps": ["apk", "android", "ios", "mobile"],
        "Music": ["music", "mp3", "flac", "album", "track", "audio"],
        "Games": ["game", "gog", "fitgirl", "repack", "steam"],
        "Books": ["ebook", "pdf", "epub", "book", "novel"],
    }


settings = Settings()
