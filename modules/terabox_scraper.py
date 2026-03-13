"""
modules/terabox_scraper.py – scrape public Terabox share pages to extract
file/folder metadata without requiring authentication.
"""

import re
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from utils.logger import logger


@dataclass
class FileInfo:
    name: str = ""
    size: int = 0  # bytes
    file_type: str = ""
    is_folder: bool = False
    file_count: int = 1
    fs_id: str = ""  # Terabox internal file-system ID
    share_id: str = ""  # short share token extracted from URL
    uk: str = ""  # uploader's user-key
    sign: str = ""
    timestamp: str = ""
    children: list = field(default_factory=list)  # for folders


# Headers that mimic a real browser request
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.terabox.com/",
}


class TeraboxScraper:
    """Extracts metadata from a public Terabox share URL."""

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        self._session.headers.update(_HEADERS)

    # ── Public API ─────────────────────────────────────────────────────────────

    def scrape(self, share_url: str) -> Optional[FileInfo]:
        """
        Scrape *share_url* and return a populated :class:`FileInfo`, or *None*
        on failure.
        """
        logger.info(f"Scraping Terabox page: {share_url}")
        share_id = self._extract_share_id(share_url)
        if not share_id:
            logger.error(f"Could not extract share ID from URL: {share_url}")
            return None

        try:
            # First fetch the share page HTML to obtain uk / sign / timestamp
            info = self._fetch_share_page(share_url, share_id)
            if info is None:
                return None

            # Fetch the file list via the internal JSON API
            file_data = self._fetch_file_list(
                share_id=info.share_id,
                uk=info.uk,
                sign=info.sign,
                timestamp=info.timestamp,
            )
            if file_data:
                self._populate_from_api(info, file_data)

            return info
        except Exception as exc:
            logger.exception(f"Scraping error for {share_url}: {exc}")
            return None

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_share_id(url: str) -> str:
        """Extract the short share-token from the URL path."""
        match = re.search(r"/s/([A-Za-z0-9_\-]+)", url)
        if match:
            return match.group(1)
        # Fallback: last path segment
        path = url.rstrip("/").split("/")[-1]
        return path if path else ""

    def _fetch_share_page(self, url: str, share_id: str) -> Optional[FileInfo]:
        """Fetch share page HTML and parse essential parameters."""
        try:
            resp = self._session.get(url, timeout=30, allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error(f"HTTP error fetching share page: {exc}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        info = FileInfo(share_id=share_id)

        # Try to extract from embedded JSON (rendered in <script> tags)
        for script in soup.find_all("script"):
            text = script.string or ""
            if not text:
                continue

            # Extract uk
            uk_match = re.search(r'"uk"\s*:\s*"?(\d+)"?', text)
            if uk_match:
                info.uk = uk_match.group(1)

            # Extract sign
            sign_match = re.search(r'"sign"\s*:\s*"([^"]+)"', text)
            if sign_match:
                info.sign = sign_match.group(1)

            # Extract timestamp
            ts_match = re.search(r'"timestamp"\s*:\s*"?(\d+)"?', text)
            if ts_match:
                info.timestamp = ts_match.group(1)

            # Extract primary file name from title
            name_match = re.search(r'"server_filename"\s*:\s*"([^"]+)"', text)
            if name_match and not info.name:
                info.name = name_match.group(1)

            # Extract is_dir flag
            if '"is_dir"' in text:
                dir_match = re.search(r'"is_dir"\s*:\s*(\d)', text)
                if dir_match:
                    info.is_folder = dir_match.group(1) == "1"

            # Extract fs_id
            fsid_match = re.search(r'"fs_id"\s*:\s*"?(\d+)"?', text)
            if fsid_match and not info.fs_id:
                info.fs_id = fsid_match.group(1)

            # Extract size
            size_match = re.search(r'"size"\s*:\s*(\d+)', text)
            if size_match and info.size == 0:
                info.size = int(size_match.group(1))

        # Fallback: page title
        if not info.name:
            title = soup.find("title")
            if title:
                info.name = title.text.strip()

        if not info.uk:
            logger.warning(f"Could not find 'uk' for share {share_id}.")

        return info

    def _fetch_file_list(
        self, share_id: str, uk: str, sign: str, timestamp: str
    ) -> Optional[dict]:
        """Call the Terabox file-list JSON API."""
        if not all([share_id, uk, sign, timestamp]):
            logger.debug("Insufficient parameters for file-list API call.")
            return None

        api_url = "https://www.terabox.com/share/list"
        params = {
            "app_id": "250528",
            "web": "1",
            "channel": "dubox",
            "clienttype": "0",
            "shorturl": share_id,
            "root": "1",
            "uk": uk,
            "sign": sign,
            "timestamp": timestamp,
            "num": "100",
            "page": "1",
            "order": "name",
            "desc": "0",
        }
        try:
            resp = self._session.get(api_url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errno") == 0:
                return data
            logger.warning(f"File-list API returned errno={data.get('errno')}")
        except Exception as exc:
            logger.warning(f"File-list API call failed: {exc}")
        return None

    @staticmethod
    def _populate_from_api(info: FileInfo, data: dict) -> None:
        """Fill *info* from the JSON file-list API response."""
        file_list = data.get("list", [])
        if not file_list:
            return

        if len(file_list) == 1:
            item = file_list[0]
            info.name = item.get("server_filename", info.name)
            info.size = int(item.get("size", info.size))
            info.is_folder = bool(item.get("isdir", info.is_folder))
            info.fs_id = str(item.get("fs_id", info.fs_id))
            info.file_count = 1
        else:
            # Multiple files → treat as folder
            info.is_folder = True
            info.file_count = len(file_list)
            info.size = sum(int(i.get("size", 0)) for i in file_list)
            info.children = [
                {
                    "name": i.get("server_filename", ""),
                    "size": int(i.get("size", 0)),
                    "fs_id": str(i.get("fs_id", "")),
                }
                for i in file_list
            ]
            if not info.name and file_list:
                info.name = file_list[0].get("server_filename", "Unknown")

        # Infer file type from extension
        if not info.is_folder and info.name:
            ext = info.name.rsplit(".", 1)[-1].lower() if "." in info.name else ""
            info.file_type = ext
