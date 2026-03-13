"""
modules/terabox_share.py – generate a public share link for a file/folder
that has been saved to the authenticated user's cloud.
"""

import time
from typing import Optional

from modules.terabox_auth import TeraboxAuth
from modules.terabox_scraper import FileInfo
from utils.logger import logger

try:
    from playwright.sync_api import BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class TeraboxShare:
    """Creates public share links for files in the user's own cloud."""

    def __init__(self, auth: TeraboxAuth):
        self._auth = auth

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate_share_link(
        self, file_info: FileInfo, dest_path: str
    ) -> Optional[str]:
        """
        Locate the saved file at *dest_path* / *file_info.name* and create a
        public share link.  Returns the share URL string or *None* on failure.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is required for share-link generation.")

        context = self._auth.get_context()
        fs_id = self._find_fs_id(context, file_info, dest_path)
        if not fs_id:
            logger.error(f"Could not find fs_id for '{file_info.name}' in '{dest_path}'")
            return None

        return self._create_share(context, fs_id, file_info.name)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _find_fs_id(
        self,
        context: "BrowserContext",
        file_info: FileInfo,
        dest_path: str,
    ) -> Optional[str]:
        """
        Query the user's file list to find the fs_id of the newly saved file.
        Retries several times to allow the copy operation to complete.
        """
        page = context.new_page()
        try:
            page.goto("https://www.terabox.com/main", wait_until="networkidle", timeout=20_000)
            cookies = {c["name"]: c["value"] for c in context.cookies()}

            for attempt in range(6):
                js = f"""
                async () => {{
                    const params = new URLSearchParams({{
                        method: 'list',
                        app_id: '250528',
                        web: '1',
                        channel: 'dubox',
                        clienttype: '0',
                        dir: '{dest_path}',
                        num: '100',
                        page: '1',
                        order: 'time',
                        desc: '1',
                    }});
                    const resp = await fetch(
                        'https://www.terabox.com/api/list?' + params.toString()
                    );
                    return resp.json();
                }}
                """
                result = page.evaluate(js)
                if isinstance(result, dict) and result.get("errno") == 0:
                    for item in result.get("list", []):
                        if item.get("server_filename") == file_info.name:
                            return str(item["fs_id"])
                logger.debug(
                    f"fs_id not found yet (attempt {attempt + 1}/6), waiting…"
                )
                time.sleep(5)
            return None
        except Exception as exc:
            logger.exception(f"Error finding fs_id: {exc}")
            return None
        finally:
            page.close()

    def _create_share(
        self, context: "BrowserContext", fs_id: str, file_name: str
    ) -> Optional[str]:
        """Call the share/set API and return the resulting short URL."""
        page = context.new_page()
        try:
            page.goto("https://www.terabox.com/main", wait_until="networkidle", timeout=20_000)
            cookies = {c["name"]: c["value"] for c in context.cookies()}
            csrf_token = cookies.get("csrfToken", "")

            js = f"""
            async () => {{
                const resp = await fetch(
                    'https://www.terabox.com/share/set',
                    {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRF-TOKEN': '{csrf_token}',
                        }},
                        body: new URLSearchParams({{
                            fid_list: '[{fs_id}]',
                            schannel: '0',
                            channel_list: '[]',
                            period: '0',
                        }}).toString(),
                    }}
                );
                return resp.json();
            }}
            """
            result = page.evaluate(js)
            if isinstance(result, dict) and result.get("errno") == 0:
                short = result.get("shorturl", "")
                if short:
                    share_url = f"https://terabox.com/s/{short}"
                    logger.info(f"Share link created: {share_url}")
                    return share_url
            logger.warning(f"share/set API returned: {result}")
            return None
        except Exception as exc:
            logger.exception(f"Error creating share link for fs_id {fs_id}: {exc}")
            return None
        finally:
            page.close()
