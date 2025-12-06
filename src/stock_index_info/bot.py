"""Telegram Bot for stock index queries with scheduled sync."""

import datetime
import logging
from functools import wraps
from typing import Callable, Coroutine, Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from stock_index_info.config import (
    TELEGRAM_BOT_TOKEN,
    ALLOWED_USER_IDS,
    DB_PATH,
    SYNC_HOUR,
    SYNC_MINUTE,
    validate_config,
)
from stock_index_info.db import (
    init_db,
    insert_constituent,
    get_stock_memberships,
    get_index_constituents,
)
from stock_index_info.scrapers.sp500 import SP500Scraper
from stock_index_info.scrapers.nasdaq100 import NASDAQ100Scraper

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def restricted(
    func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    """Decorator to restrict bot access to allowed users only."""

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if user is None or user.id not in ALLOWED_USER_IDS:
            logger.warning(f"Unauthorized access attempt by user {user}")
            if update.message:
                await update.message.reply_text(
                    "Sorry, you are not authorized to use this bot."
                )
            return
        return await func(update, context)

    return wrapped


async def _do_sync() -> list[str]:
    """Execute sync logic and return results."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(DB_PATH)

    scrapers = [SP500Scraper(), NASDAQ100Scraper()]
    results: list[str] = []

    for scraper in scrapers:
        try:
            records = scraper.fetch()
            for record in records:
                insert_constituent(conn, record)
            results.append(f"{scraper.index_name}: {len(records)} records")
        except Exception as e:
            results.append(f"{scraper.index_name}: Error - {e}")
            logger.error(f"Error syncing {scraper.index_name}: {e}")

    conn.close()
    return results


async def scheduled_sync(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled job to sync data from Wikipedia daily.

    This runs automatically at the configured time (default 2:00 AM).
    """
    logger.info("Starting scheduled sync...")

    try:
        results = await _do_sync()
        logger.info(f"Scheduled sync complete: {results}")
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")


@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if update.message:
        await update.message.reply_text(
            "Welcome to Stock Index Info Bot!\n\n"
            "Commands:\n"
            "/query <TICKER> - Query which indices a stock belongs to\n"
            "/constituents <INDEX> - List constituents (sp500 or nasdaq100)\n"
            "/sync - Sync data from Wikipedia manually\n"
            "/status - Show bot status and next sync time\n"
            "/help - Show this help message\n\n"
            "You can also just send a ticker symbol directly!\n\n"
            f"Auto-sync runs daily at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d}"
        )


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if update.message:
        await update.message.reply_text(
            "Stock Index Info Bot\n\n"
            "Query which US stock indices (S&P 500, NASDAQ 100) a stock belongs to.\n\n"
            "Commands:\n"
            "/query <TICKER> - Query stock index membership\n"
            "  Example: /query AAPL\n\n"
            "/constituents <INDEX> - List current constituents\n"
            "  Example: /constituents sp500\n\n"
            "/sync - Sync data from Wikipedia manually\n\n"
            "/status - Show bot status\n\n"
            "Or just send a ticker symbol like: AAPL\n\n"
            f"Data is automatically synced daily at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d}"
        )


@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - show bot status and next sync time."""
    if not update.message:
        return

    # Get next scheduled sync time
    jobs = context.job_queue.get_jobs_by_name("daily_sync") if context.job_queue else []
    next_sync = "Not scheduled"
    if jobs:
        next_run = jobs[0].next_t
        if next_run:
            next_sync = next_run.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Check database status
    db_status = "Not initialized"
    if DB_PATH.exists():
        try:
            conn = init_db(DB_PATH)
            cursor = conn.execute("SELECT COUNT(*) FROM constituents")
            count = cursor.fetchone()[0]
            conn.close()
            db_status = f"{count} records"
        except Exception as e:
            db_status = f"Error: {e}"

    await update.message.reply_text(
        "*Bot Status*\n\n"
        f"Database: {db_status}\n"
        f"Next sync: {next_sync}\n"
        f"Sync schedule: Daily at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d}",
        parse_mode="Markdown",
    )


@restricted
async def query_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /query command."""
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("Usage: /query <TICKER>\nExample: /query AAPL")
        return

    ticker = context.args[0].upper()
    await _query_ticker(update, ticker)


@restricted
async def ticker_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct ticker messages."""
    if not update.message or not update.message.text:
        return

    ticker = update.message.text.strip().upper()
    # Basic validation: 1-5 uppercase letters
    if not ticker.isalpha() or len(ticker) > 5:
        return

    await _query_ticker(update, ticker)


async def _query_ticker(update: Update, ticker: str) -> None:
    """Query and respond with ticker information."""
    if not update.message:
        return

    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        await update.message.reply_text(
            "Database not initialized. Please run /sync first or wait for auto-sync."
        )
        return

    conn = init_db(DB_PATH)
    try:
        memberships = get_stock_memberships(conn, ticker)

        if not memberships:
            await update.message.reply_text(
                f"{ticker} not found in any tracked index."
            )
            return

        # Build response
        lines: list[str] = [f"*{ticker}*", "", "Index Membership:", "```"]
        lines.append(f"{'Index':<12} {'Added':<12} {'Removed':<12} {'Years':>6}")
        lines.append("-" * 44)

        for m in memberships:
            removed_str = m.removed_date.isoformat() if m.removed_date else "-"
            lines.append(
                f"{m.index_name:<12} {m.added_date.isoformat():<12} {removed_str:<12} {m.years_in_index:>6.1f}"
            )

        lines.append("```")

        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown"
        )
    finally:
        conn.close()


@restricted
async def constituents_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /constituents command."""
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /constituents <INDEX>\n"
            "Example: /constituents sp500\n"
            "Available indices: sp500, nasdaq100"
        )
        return

    index_code = context.args[0].lower()
    if index_code not in ("sp500", "nasdaq100"):
        await update.message.reply_text(
            "Invalid index. Available indices: sp500, nasdaq100"
        )
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        await update.message.reply_text(
            "Database not initialized. Please run /sync first or wait for auto-sync."
        )
        return

    conn = init_db(DB_PATH)
    try:
        tickers = get_index_constituents(conn, index_code)

        if not tickers:
            await update.message.reply_text(f"No constituents found for {index_code}")
            return

        index_name = "S&P 500" if index_code == "sp500" else "NASDAQ 100"
        await update.message.reply_text(
            f"*{index_name}* constituents ({len(tickers)}):\n\n"
            f"{', '.join(tickers)}",
            parse_mode="Markdown",
        )
    finally:
        conn.close()


@restricted
async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sync command - manual sync."""
    if not update.message:
        return

    await update.message.reply_text("Starting data sync from Wikipedia...")

    results = await _do_sync()

    await update.message.reply_text(
        "Sync complete!\n\n" + "\n".join(results)
    )


def main() -> None:
    """Start the Telegram bot with scheduled sync."""
    errors = validate_config()
    if errors:
        for error in errors:
            logger.error(error)
        raise SystemExit(1)

    logger.info(f"Starting bot with {len(ALLOWED_USER_IDS)} allowed users")
    logger.info(f"Scheduled sync at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d} daily")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("query", query_command))
    application.add_handler(CommandHandler("constituents", constituents_command))
    application.add_handler(CommandHandler("sync", sync_command))

    # Handle direct ticker messages (text messages that look like tickers)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ticker_message)
    )

    # Schedule daily sync using JobQueue
    job_queue = application.job_queue
    if job_queue:
        sync_time = datetime.time(hour=SYNC_HOUR, minute=SYNC_MINUTE)
        job_queue.run_daily(
            scheduled_sync,
            time=sync_time,
            name="daily_sync",
        )
        logger.info(f"Scheduled daily sync job at {sync_time}")

    # Start the bot (runs forever)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
