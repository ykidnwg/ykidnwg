"""
modules/terabox_auth.py – handles Terabox login via Playwright headless browser
and persists the session cookies so subsequent requests reuse the same session.
"""

import json
import time
from pathlib import Path
from typing import Optional

from config import settings
from utils.logger import logger

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright not installed – browser automation unavailable.")


TERABOX_LOGIN_URL = "https://www.terabox.com/login"
TERABOX_HOME_URL = "https://www.terabox.com/main"


class TeraboxAuth:
    """Manages a persistent Playwright browser session for Terabox."""

    def __init__(self):
        self._playwright = None
        self._browser: "Optional[Browser]" = None
        self._context: "Optional[BrowserContext]" = None
        self._cookie_file = Path(settings.TERABOX_COOKIE_FILE)
        self._cookie_file.parent.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_context(self) -> "BrowserContext":
        """Return (or lazily create) an authenticated browser context."""
        if self._context is None:
            self._start_browser()
            if self._cookie_file.exists():
                self._load_cookies()
                if not self._verify_login():
                    logger.info("Saved session expired – performing fresh login.")
                    self._do_login()
            else:
                self._do_login()
        return self._context

    def close(self) -> None:
        """Gracefully close browser and Playwright instance."""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as exc:
            logger.warning(f"Error closing browser: {exc}")
        finally:
            self._context = None
            self._browser = None
            self._playwright = None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _start_browser(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "playwright is not installed. Run: pip install playwright && playwright install"
            )
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        logger.debug("Playwright browser started.")

    def _do_login(self) -> None:
        """Perform interactive login and persist cookies."""
        page = self._context.new_page()
        try:
            logger.info("Navigating to Terabox login page…")
            page.goto(TERABOX_LOGIN_URL, wait_until="networkidle", timeout=30_000)
            time.sleep(2)

            # Fill email
            page.fill('input[name="userName"], input[type="email"]', settings.TERABOX_EMAIL)
            time.sleep(0.5)

            # Fill password
            page.fill('input[name="password"], input[type="password"]', settings.TERABOX_PASSWORD)
            time.sleep(0.5)

            # Submit
            page.click('button[type="submit"], .submit-btn, [data-te-ripple-init]')
            page.wait_for_url("**/main**", timeout=30_000)

            logger.info("Terabox login successful.")
            self._save_cookies()
        except Exception as exc:
            logger.error(f"Login failed: {exc}")
            raise
        finally:
            page.close()

    def _verify_login(self) -> bool:
        """Check whether the loaded cookies still grant an authenticated session."""
        page = self._context.new_page()
        try:
            page.goto(TERABOX_HOME_URL, wait_until="networkidle", timeout=20_000)
            return "login" not in page.url and "/main" in page.url
        except Exception:
            return False
        finally:
            page.close()

    def _save_cookies(self) -> None:
        cookies = self._context.cookies()
        self._cookie_file.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
        logger.debug(f"Session cookies saved to {self._cookie_file}")

    def _load_cookies(self) -> None:
        cookies = json.loads(self._cookie_file.read_text())
        self._context.add_cookies(cookies)
        logger.debug(f"Session cookies loaded from {self._cookie_file}")
