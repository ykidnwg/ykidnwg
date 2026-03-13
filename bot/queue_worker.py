"""
bot/queue_worker.py – background worker that pulls jobs from the queue,
processes them via JobManager, and sends Telegram notifications.
"""

from __future__ import annotations

import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional

from config import settings
from utils.logger import logger
from services.queue_manager import QueueManager
from services.job_manager import JobManager
from modules.terabox_auth import TeraboxAuth
from bot.telegram_bot import notify_channel_sync


class QueueWorker:
    """
    Pulls links from *queue_manager* and processes them using a thread pool.
    Keeps a single :class:`TeraboxAuth` instance so the browser session is
    reused across jobs.
    """

    def __init__(self, queue_manager: QueueManager, num_workers: Optional[int] = None):
        self._queue = queue_manager
        self._num_workers = num_workers or settings.MAX_WORKERS
        self._auth = TeraboxAuth()
        self._executor = ThreadPoolExecutor(max_workers=self._num_workers)
        self._running = False
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the main dispatch loop (blocking)."""
        self._running = True
        self._setup_signals()
        logger.info(
            f"Queue worker started with {self._num_workers} parallel worker(s)."
        )

        try:
            while self._running:
                link = self._queue.dequeue(timeout=5)
                if link:
                    self._queue.mark_processing(link)
                    future = self._executor.submit(self._process_job, link)
                    with self._lock:
                        self._futures[link] = future
                else:
                    # Clean up completed futures
                    self._gc_futures()
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the worker to stop gracefully."""
        self._running = False

    # ── Job execution ─────────────────────────────────────────────────────────

    def _process_job(self, link: str) -> None:
        job_mgr = JobManager(self._auth)
        try:
            result = job_mgr.process(link)
            logger.bind(link=link).info(
                f"Job finished – status={result.status}"
            )

            if result.status == "SUCCESS":
                notify_channel_sync(
                    file_name=result.file_name,
                    file_size=result.file_size,
                    file_count=result.file_count,
                    share_link=result.share_link,
                )
                self._queue.mark_done(link)
            elif result.status == "DUPLICATE":
                logger.info(f"Duplicate – skipping Telegram notify for {link}")
                self._queue.mark_done(link)
            else:
                self._queue.mark_failed(link)
        except Exception as exc:
            logger.exception(f"Unhandled error processing {link}: {exc}")
            self._queue.mark_failed(link)
        finally:
            with self._lock:
                self._futures.pop(link, None)

    # ── Housekeeping ──────────────────────────────────────────────────────────

    def _gc_futures(self) -> None:
        with self._lock:
            done = [k for k, f in self._futures.items() if f.done()]
            for k in done:
                del self._futures[k]

    def _shutdown(self) -> None:
        logger.info("Shutting down queue worker…")
        self._executor.shutdown(wait=True)
        self._auth.close()
        logger.info("Queue worker stopped.")

    def _setup_signals(self) -> None:
        def _handler(sig, frame):
            logger.info(f"Received signal {sig} – stopping worker.")
            self.stop()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
