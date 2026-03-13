"""
services/queue_manager.py – abstracts over Redis (preferred) with a SQLite
fallback so the bot runs without Redis if needed.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from config import settings
from utils.logger import logger

try:
    import redis as redis_lib

    _redis_client: Optional[redis_lib.Redis] = None


    def _get_redis() -> redis_lib.Redis:
        global _redis_client
        if _redis_client is None:
            _redis_client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True,
                socket_connect_timeout=5,
            )
        return _redis_client

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

QUEUE_KEY = "terabox:queue"
PROCESSING_KEY = "terabox:processing"
FAILED_KEY = "terabox:failed"


class QueueManager:
    """
    Thread-safe job queue.

    Uses Redis RPUSH / BLPOP when Redis is available, otherwise falls back to
    the SQLite-backed :class:`~database.models.Job` table so that no external
    service is required.
    """

    def __init__(self):
        self._use_redis = REDIS_AVAILABLE and self._redis_ping()

    # ── Public API ────────────────────────────────────────────────────────────

    def enqueue(self, link: str) -> bool:
        """Add *link* to the pending queue.  Returns False if already queued."""
        if self._use_redis:
            return self._redis_enqueue(link)
        return self._db_enqueue(link)

    def dequeue(self, timeout: int = 5) -> Optional[str]:
        """Block until a link becomes available and return it."""
        if self._use_redis:
            return self._redis_dequeue(timeout)
        return self._db_dequeue()

    def mark_processing(self, link: str) -> None:
        if self._use_redis:
            try:
                _get_redis().sadd(PROCESSING_KEY, link)
            except Exception as exc:
                logger.warning(f"Redis mark_processing error: {exc}")

    def mark_done(self, link: str) -> None:
        if self._use_redis:
            try:
                _get_redis().srem(PROCESSING_KEY, link)
            except Exception as exc:
                logger.warning(f"Redis mark_done error: {exc}")

    def mark_failed(self, link: str) -> None:
        if self._use_redis:
            try:
                r = _get_redis()
                r.srem(PROCESSING_KEY, link)
                r.rpush(FAILED_KEY, link)
            except Exception as exc:
                logger.warning(f"Redis mark_failed error: {exc}")

    def queue_size(self) -> int:
        if self._use_redis:
            try:
                return _get_redis().llen(QUEUE_KEY)
            except Exception:
                pass
        return self._db_queue_size()

    def failed_size(self) -> int:
        if self._use_redis:
            try:
                return _get_redis().llen(FAILED_KEY)
            except Exception:
                pass
        return 0

    # ── Redis helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _redis_ping() -> bool:
        try:
            _get_redis().ping()
            logger.info("Redis connection established.")
            return True
        except Exception as exc:
            logger.warning(f"Redis not available ({exc}), falling back to SQLite queue.")
            return False

    @staticmethod
    def _redis_enqueue(link: str) -> bool:
        try:
            r = _get_redis()
            # Avoid duplicates: check processing set and queue list
            if r.sismember(PROCESSING_KEY, link):
                return False
            # Check queue for duplicate (O(n) but queue should be small)
            existing = r.lrange(QUEUE_KEY, 0, -1)
            if link in existing:
                return False
            r.rpush(QUEUE_KEY, link)
            return True
        except Exception as exc:
            logger.error(f"Redis enqueue error: {exc}")
            return False

    @staticmethod
    def _redis_dequeue(timeout: int) -> Optional[str]:
        try:
            result = _get_redis().blpop(QUEUE_KEY, timeout=timeout)
            if result:
                return result[1]
        except Exception as exc:
            logger.error(f"Redis dequeue error: {exc}")
        return None

    # ── SQLite helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _db_enqueue(link: str) -> bool:
        from database.models import Job, get_session
        session = get_session()
        try:
            existing = session.query(Job).filter(Job.link == link).first()
            if existing:
                return False
            job = Job(link=link, status="PENDING")
            session.add(job)
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.error(f"DB enqueue error: {exc}")
            return False
        finally:
            session.close()

    @staticmethod
    def _db_dequeue() -> Optional[str]:
        from database.models import Job, get_session
        session = get_session()
        try:
            job = (
                session.query(Job)
                .filter(Job.status == "PENDING")
                .order_by(Job.created_at.asc())
                .with_for_update(skip_locked=True)
                .first()
            )
            if job:
                job.status = "RUNNING"
                session.commit()
                return job.link
        except Exception as exc:
            session.rollback()
            logger.error(f"DB dequeue error: {exc}")
        finally:
            session.close()
        return None

    @staticmethod
    def _db_queue_size() -> int:
        from database.models import Job, get_session
        session = get_session()
        try:
            return session.query(Job).filter(Job.status == "PENDING").count()
        finally:
            session.close()
