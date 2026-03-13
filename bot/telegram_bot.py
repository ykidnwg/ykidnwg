"""
bot/telegram_bot.py – Telegram bot that accepts share links from users and
forwards them to the processing queue, then sends results to the channel.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from config import settings
from utils.logger import logger
from utils.validator import is_valid_terabox_link, extract_links_from_text
from utils.helpers import build_telegram_message

try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed – Telegram integration disabled.")


class TelegramBot:
    """Wraps python-telegram-bot and integrates with the queue."""

    def __init__(self, queue_manager):
        self._queue = queue_manager
        self._app: Optional["Application"] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the bot in polling mode (blocking)."""
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError(
                "python-telegram-bot is not installed. "
                "Run: pip install python-telegram-bot"
            )
        if not settings.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")

        self._app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()
        logger.info("Telegram bot starting (polling)…")
        self._app.run_polling(drop_pending_updates=True)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _register_handlers(self) -> None:
        app = self._app
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "👋 Hi! Send me a Terabox link and I'll save it to the cloud for you.\n\n"
            "Supported domains:\n"
            "• terabox.com\n"
            "• 1024terabox.com\n"
            "• teraboxapp.com\n\n"
            "Use /status to check queue status."
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "📖 *Terabox Bot Help*\n\n"
            "Send any Terabox share link and the bot will:\n"
            "1️⃣  Scrape the file metadata\n"
            "2️⃣  Save the file to your cloud\n"
            "3️⃣  Create a new share link\n"
            "4️⃣  Post the result to the channel\n\n"
            "/status – show queue statistics",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        q_size = self._queue.queue_size()
        failed = self._queue.failed_size()
        await update.message.reply_text(
            f"📊 *Queue Status*\n\n"
            f"⏳ Pending : {q_size}\n"
            f"❌ Failed  : {failed}",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        text = update.message.text or ""
        links = extract_links_from_text(text)

        if not links:
            # Check if the message looks like a URL attempt
            if "terabox" in text.lower():
                await update.message.reply_text(
                    "⚠️ That doesn't look like a valid Terabox link.  "
                    "Please send a link from terabox.com, 1024terabox.com, or teraboxapp.com."
                )
            return

        added = 0
        for link in links:
            if self._queue.enqueue(link):
                added += 1
                logger.info(f"Queued link from Telegram: {link}")

        if added:
            await update.message.reply_text(
                f"✅ {added} link(s) added to the processing queue.\n"
                "You'll receive the result in the channel shortly."
            )
        else:
            await update.message.reply_text(
                "ℹ️ This link is already in the queue or has been processed."
            )

    # ── Channel notification ──────────────────────────────────────────────────

    @staticmethod
    async def notify_channel(
        file_name: str,
        file_size: int,
        file_count: int,
        share_link: str,
        is_folder: bool = False,
    ) -> None:
        """Send a result notification to the configured Telegram channel."""
        if not TELEGRAM_AVAILABLE or not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram not configured – skipping channel notification.")
            return

        message = build_telegram_message(
            file_name=file_name,
            file_size=file_size,
            file_count=file_count,
            share_link=share_link,
            is_folder=is_folder,
        )

        try:
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            async with bot:
                await bot.send_message(
                    chat_id=settings.TELEGRAM_CHANNEL_ID,
                    text=message,
                )
            logger.info(f"Telegram notification sent for: {file_name}")
        except Exception as exc:
            logger.error(f"Failed to send Telegram notification: {exc}")


def notify_channel_sync(
    file_name: str,
    file_size: int,
    file_count: int,
    share_link: str,
    is_folder: bool = False,
) -> None:
    """Synchronous wrapper around :func:`TelegramBot.notify_channel`."""
    try:
        asyncio.run(
            TelegramBot.notify_channel(
                file_name=file_name,
                file_size=file_size,
                file_count=file_count,
                share_link=share_link,
                is_folder=is_folder,
            )
        )
    except Exception as exc:
        logger.error(f"notify_channel_sync error: {exc}")
