"""utils/helpers.py – miscellaneous helper utilities."""

import re
import hashlib
import math
from pathlib import Path

from config import settings
from utils.logger import logger


def format_file_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string (KB / MB / GB)."""
    if size_bytes == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    exp = min(int(math.log(size_bytes, 1024)), len(units) - 1)
    value = size_bytes / (1024 ** exp)
    return f"{value:.2f} {units[exp]}"


def slugify(text: str) -> str:
    """Return a filesystem-safe version of *text*."""
    text = re.sub(r"[^\w\s\-.]", "", text)
    text = re.sub(r"[\s]+", "_", text.strip())
    return text[:200]


def sha256_of_string(value: str) -> str:
    """Return the SHA-256 hex digest of *value*."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def categorize_file(file_name: str) -> str:
    """
    Determine the best category folder for *file_name* based on keyword
    matching defined in ``settings.CATEGORY_MAP``.  Returns the folder name
    or an empty string when no match is found (caller should use a default).
    """
    lower = file_name.lower()
    for category, keywords in settings.CATEGORY_MAP.items():
        if any(kw in lower for kw in keywords):
            return category
    return "Others"


def build_telegram_message(
    file_name: str,
    file_size: int,
    file_count: int,
    share_link: str,
    is_folder: bool = False,
) -> str:
    """Compose the Telegram notification message."""
    icon = "📂 Folder" if is_folder else "📄 File"
    size_str = format_file_size(file_size)
    return (
        f"📂 FILE BERHASIL DISIMPAN\n\n"
        f"{icon}\n\n"
        f"📄 Nama   : {file_name}\n"
        f"📦 Size   : {size_str}\n"
        f"📁 Jumlah : {file_count} file(s)\n"
        f"🔗 Download : {share_link}"
    )


def ensure_dirs() -> None:
    """Create required directories if they do not exist."""
    for d in ("logs", "database"):
        Path(d).mkdir(parents=True, exist_ok=True)
