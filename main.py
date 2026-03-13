"""
main.py – entry point for the Terabox Automation Bot.

Usage:
  python main.py                   # start all components
  python main.py --worker-only     # queue worker only (no Telegram bot)
  python main.py --bot-only        # Telegram bot only (no queue worker)
  python main.py --file links.txt  # enqueue links from file then process
  python main.py --link <url>      # enqueue a single link then process
"""

import argparse
import sys
import threading
from pathlib import Path

from config import settings
from utils.helpers import ensure_dirs
from utils.logger import logger
from utils.validator import read_links_from_file, is_valid_terabox_link
from database.models import init_db
from services.queue_manager import QueueManager
from bot.queue_worker import QueueWorker
from bot.telegram_bot import TelegramBot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Terabox Automation Bot",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--worker-only",
        action="store_true",
        help="Start queue worker only (skip Telegram bot polling)",
    )
    parser.add_argument(
        "--bot-only",
        action="store_true",
        help="Start Telegram bot only (skip queue worker)",
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="Enqueue links from a text file (one link per line)",
    )
    parser.add_argument(
        "--link",
        metavar="URL",
        help="Enqueue a single Terabox link",
    )
    return parser.parse_args()


def enqueue_from_file(path: str, queue: QueueManager) -> int:
    links = read_links_from_file(path)
    added = 0
    for link in links:
        if queue.enqueue(link):
            added += 1
            logger.info(f"Enqueued: {link}")
        else:
            logger.debug(f"Already queued / processed: {link}")
    logger.info(f"Enqueued {added}/{len(links)} links from {path}")
    return added


def main() -> None:
    ensure_dirs()
    args = parse_args()

    # Initialise database
    init_db()
    logger.info("Database initialised.")

    # Set up queue
    queue = QueueManager()

    # Optional: enqueue from file or single link
    if args.file:
        enqueue_from_file(args.file, queue)
    if args.link:
        if is_valid_terabox_link(args.link):
            queue.enqueue(args.link)
            logger.info(f"Enqueued single link: {args.link}")
        else:
            logger.error(f"Invalid link: {args.link}")
            sys.exit(1)

    threads: list[threading.Thread] = []

    # Queue worker thread
    if not args.bot_only:
        worker = QueueWorker(queue)
        worker_thread = threading.Thread(
            target=worker.start, name="QueueWorker", daemon=True
        )
        threads.append(worker_thread)
        worker_thread.start()
        logger.info("Queue worker thread started.")

    # Telegram bot thread
    if not args.worker_only:
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning(
                "TELEGRAM_BOT_TOKEN not set – Telegram bot will not start. "
                "Set it in .env to enable."
            )
        else:
            bot = TelegramBot(queue)
            bot_thread = threading.Thread(
                target=bot.start, name="TelegramBot", daemon=True
            )
            threads.append(bot_thread)
            bot_thread.start()
            logger.info("Telegram bot thread started.")

    if not threads:
        logger.error("No components started. Provide --worker-only or --bot-only flag.")
        sys.exit(1)

    logger.info("Terabox Bot is running. Press Ctrl+C to stop.")
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received – shutting down.")


if __name__ == "__main__":
    main()
