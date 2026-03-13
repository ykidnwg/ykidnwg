"""
modules/terabox_save.py – save a public Terabox file/folder to the logged-in
user's own cloud storage using browser automation via Playwright.
"""

import time
import re
from typing import Optional

from modules.terabox_scraper import FileInfo
from modules.terabox_auth import TeraboxAuth
from config import settings
from utils.logger import logger
from utils.helpers import categorize_file, slugify

try:
    from playwright.sync_api import BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


SAVE_API = "https://www.terabox.com/share/transfer"


class TeraboxSave:
    """Handles the 'Save to my cloud' operation."""

    def __init__(self, auth: TeraboxAuth):
        self._auth = auth

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self, file_info: FileInfo, dest_folder: str = "/") -> bool:
        """
        Save the file / folder described by *file_info* into the authenticated
        user's Terabox cloud at *dest_folder*.

        Returns *True* on success, *False* otherwise.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is required for save operations.")

        if settings.ENABLE_AUTO_CATEGORIZE and file_info.name:
            category = categorize_file(file_info.name)
            dest_folder = f"/{category}"
            logger.info(f"Auto-categorised '{file_info.name}' → {dest_folder}")
        else:
            category = "Others"

        # Ensure destination folder exists
        context = self._auth.get_context()
        self._ensure_folder(context, dest_folder)

        return self._transfer_via_api(context, file_info, dest_folder)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _transfer_via_api(
        self, context: "BrowserContext", file_info: FileInfo, dest_path: str
    ) -> bool:
        """Use the Terabox share/transfer API endpoint to copy the file."""
        page = context.new_page()
        try:
            # Navigate to trigger cookie injection into the page context
            page.goto("https://www.terabox.com/main", wait_until="networkidle", timeout=30_000)
            time.sleep(1)

            # Build CSRF token from page cookies
            cookies = {c["name"]: c["value"] for c in context.cookies()}
            csrf_token = cookies.get("csrfToken", "")

            # Perform fetch via page.evaluate so same-origin cookies are sent
            js = f"""
            async () => {{
                const params = new URLSearchParams({{
                    app_id: '250528',
                    web: '1',
                    channel: 'dubox',
                    clienttype: '0',
                    shorturl: '{file_info.share_id}',
                    to: '{dest_path}',
                    fsidlist: '[{file_info.fs_id}]',
                }});
                const resp = await fetch(
                    'https://www.terabox.com/share/transfer?' + params.toString(),
                    {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRF-TOKEN': '{csrf_token}',
                        }},
                    }}
                );
                return resp.json();
            }}
            """
            result = page.evaluate(js)
            errno = result.get("errno", -1) if isinstance(result, dict) else -1
            if errno == 0:
                logger.info(f"File saved successfully to {dest_path}")
                return True
            logger.warning(f"Transfer API returned errno={errno}: {result}")
            return self._save_via_ui(page, file_info, dest_path)
        except Exception as exc:
            logger.exception(f"Error during file save: {exc}")
            return False
        finally:
            page.close()

    def _save_via_ui(self, page, file_info: FileInfo, dest_path: str) -> bool:
        """Fallback: drive the 'Save' button in the share page UI."""
        try:
            logger.info("Falling back to UI-based save flow.")
            share_url = f"https://www.terabox.com/s/{file_info.share_id}"
            page.goto(share_url, wait_until="networkidle", timeout=30_000)
            time.sleep(2)

            # Click the Save / 保存 button
            save_btn = page.locator(
                'button:has-text("Save"), button:has-text("保存"), '
                '[data-key="save"], .save-btn'
            ).first
            save_btn.click(timeout=10_000)
            time.sleep(1)

            # Choose destination folder if a dialog appears
            try:
                page.locator('[class*="folder-item"], [class*="tree-item"]').first.click(
                    timeout=5_000
                )
            except Exception:
                pass  # no folder dialog

            # Confirm
            try:
                page.locator('button:has-text("OK"), button:has-text("确定")').first.click(
                    timeout=5_000
                )
            except Exception:
                pass

            time.sleep(3)
            logger.info("UI-based save completed.")
            return True
        except Exception as exc:
            logger.error(f"UI-based save failed: {exc}")
            return False

    def _ensure_folder(self, context: "BrowserContext", path: str) -> None:
        """Create *path* in the cloud if it does not already exist."""
        if path == "/":
            return
        page = context.new_page()
        try:
            page.goto("https://www.terabox.com/main", wait_until="networkidle", timeout=20_000)
            cookies = {c["name"]: c["value"] for c in context.cookies()}
            csrf_token = cookies.get("csrfToken", "")

            js = f"""
            async () => {{
                const resp = await fetch(
                    'https://www.terabox.com/api/create',
                    {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRF-TOKEN': '{csrf_token}',
                        }},
                        body: new URLSearchParams({{
                            path: '{path}',
                            isdir: '1',
                            block_list: '[]',
                        }}).toString(),
                    }}
                );
                return resp.json();
            }}
            """
            result = page.evaluate(js)
            logger.debug(f"Ensure folder '{path}' result: {result}")
        except Exception as exc:
            logger.warning(f"Could not ensure folder '{path}': {exc}")
        finally:
            page.close()
