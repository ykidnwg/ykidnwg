"""utils/validator.py – link and input validation."""

from urllib.parse import urlparse

from config import settings
from utils.logger import logger


def is_valid_terabox_link(url: str) -> bool:
    """Return True if *url* is a recognised Terabox share link."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            logger.debug(f"Invalid scheme for URL: {url}")
            return False
        netloc = parsed.netloc.lower()
        if netloc in settings.TERABOX_VALID_DOMAINS:
            return True
        logger.debug(f"Domain not in whitelist: {netloc} for URL: {url}")
        return False
    except Exception as exc:
        logger.warning(f"URL validation error for '{url}': {exc}")
        return False


def extract_links_from_text(text: str) -> list:
    """Extract all Terabox links from a block of text."""
    import re as _re
    links = []
    # Match http(s) URLs; stop at whitespace or common trailing punctuation
    for token in _re.findall(r'https?://\S+', text):
        token = token.rstrip(".,;!?)'\"")
        if is_valid_terabox_link(token):
            links.append(token)
    return links


def read_links_from_file(filepath: str) -> list:
    """Read and validate links from a plain-text file (one per line)."""
    links = []
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line and not line.startswith("#"):
                    if is_valid_terabox_link(line):
                        links.append(line)
                    else:
                        logger.warning(f"Skipping invalid link in file: {line}")
    except FileNotFoundError:
        logger.error(f"Links file not found: {filepath}")
    except OSError as exc:
        logger.error(f"Error reading links file '{filepath}': {exc}")
    return links
