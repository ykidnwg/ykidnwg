"""
services/job_manager.py – orchestrates the full pipeline for a single link:
validate → scrape → save → share → notify → log.
"""

from __future__ import annotations

import time
from typing import Optional

from config import settings
from utils.logger import logger
from utils.validator import is_valid_terabox_link
from utils.helpers import categorize_file, build_telegram_message
from modules.terabox_auth import TeraboxAuth
from modules.terabox_scraper import TeraboxScraper, FileInfo
from modules.terabox_save import TeraboxSave
from modules.terabox_share import TeraboxShare


class JobResult:
    def __init__(
        self,
        link: str,
        status: str,
        file_name: str = "",
        file_size: int = 0,
        file_count: int = 0,
        share_link: str = "",
        error: str = "",
    ):
        self.link = link
        self.status = status  # SUCCESS / FAILED / DUPLICATE / RETRY
        self.file_name = file_name
        self.file_size = file_size
        self.file_count = file_count
        self.share_link = share_link
        self.error = error


class JobManager:
    """
    Processes a single Terabox link through the complete pipeline with retries.
    """

    def __init__(self, auth: Optional[TeraboxAuth] = None):
        self._auth = auth or TeraboxAuth()
        self._scraper = TeraboxScraper()
        self._saver = TeraboxSave(self._auth)
        self._sharer = TeraboxShare(self._auth)

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self, link: str) -> JobResult:
        """Run the pipeline for *link* with automatic retries."""
        logger.info(f"Processing link: {link}")

        # ① Validate
        if not is_valid_terabox_link(link):
            logger.warning(f"Invalid Terabox link: {link}")
            return JobResult(link=link, status="FAILED", error="Invalid link")

        # ② Duplicate check
        dup = self._check_duplicate(link)
        if dup:
            logger.info(f"Duplicate detected for link: {link}")
            return JobResult(
                link=link,
                status="DUPLICATE",
                file_name=dup.file_name,
                share_link=dup.share_link or "",
            )

        # ③ Process with retries
        last_error = ""
        for attempt in range(1, settings.RETRY_COUNT + 1):
            try:
                result = self._run_pipeline(link)
                if result.status == "SUCCESS":
                    self._record_success(link, result)
                    return result
                last_error = result.error
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"Attempt {attempt}/{settings.RETRY_COUNT} failed: {exc}")

            if attempt < settings.RETRY_COUNT:
                logger.info(
                    f"Retrying in {settings.RETRY_DELAY}s "
                    f"(attempt {attempt}/{settings.RETRY_COUNT})…"
                )
                time.sleep(settings.RETRY_DELAY)

        logger.error(f"All retries exhausted for: {link}")
        self._record_failure(link, last_error)
        return JobResult(link=link, status="FAILED", error=last_error)

    # ── Pipeline steps ─────────────────────────────────────────────────────────

    def _run_pipeline(self, link: str) -> JobResult:
        # Scrape
        file_info = self._scraper.scrape(link)
        if file_info is None:
            return JobResult(link=link, status="FAILED", error="Scraping failed")

        logger.info(
            f"Scraped: name={file_info.name!r}, size={file_info.size}, "
            f"folder={file_info.is_folder}"
        )

        # Determine destination
        if settings.ENABLE_AUTO_CATEGORIZE:
            category = categorize_file(file_info.name)
            dest_path = f"/{category}"
        else:
            dest_path = "/"

        # Save
        saved = self._saver.save(file_info, dest_path)
        if not saved:
            return JobResult(link=link, status="FAILED", error="Save to cloud failed")

        # Generate share link
        share_link = self._sharer.generate_share_link(file_info, dest_path)
        if not share_link:
            return JobResult(link=link, status="FAILED", error="Share link generation failed")

        return JobResult(
            link=link,
            status="SUCCESS",
            file_name=file_info.name,
            file_size=file_info.size,
            file_count=file_info.file_count,
            share_link=share_link,
        )

    # ── Duplicate detection ────────────────────────────────────────────────────

    @staticmethod
    def _check_duplicate(link: str):
        """Return a SeenFile record if this link was already processed."""
        from database.models import Job, get_session
        session = get_session()
        try:
            job = (
                session.query(Job)
                .filter(Job.link == link, Job.status == "SUCCESS")
                .first()
            )
            return job
        except Exception as exc:
            logger.warning(f"Duplicate check failed: {exc}")
            return None
        finally:
            session.close()

    # ── DB persistence ─────────────────────────────────────────────────────────

    @staticmethod
    def _record_success(link: str, result: "JobResult") -> None:
        from database.models import Job, get_session
        from datetime import datetime
        session = get_session()
        try:
            job = session.query(Job).filter(Job.link == link).first()
            if not job:
                job = Job(link=link)
                session.add(job)
            job.status = "SUCCESS"
            job.file_name = result.file_name
            job.file_size = result.file_size
            job.file_count = result.file_count
            job.share_link = result.share_link
            job.updated_at = datetime.utcnow()
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error(f"Failed to record success for {link}: {exc}")
        finally:
            session.close()

    @staticmethod
    def _record_failure(link: str, error: str) -> None:
        from database.models import Job, get_session
        from datetime import datetime
        session = get_session()
        try:
            job = session.query(Job).filter(Job.link == link).first()
            if not job:
                job = Job(link=link)
                session.add(job)
            job.status = "FAILED"
            job.error_message = error
            job.updated_at = datetime.utcnow()
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error(f"Failed to record failure for {link}: {exc}")
        finally:
            session.close()
