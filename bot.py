"""
Telegram bot that integrates with Bird.com WhatsApp API.

Commands:
    /start       - Welcome message and overview
    /help        - List all available commands
    /send        - Send a WhatsApp message to a single number
                   Usage: /send <phone> [var1] [var2] ...
    /bulk        - Upload a CSV/Excel file and send messages in bulk
                   (follow-up document upload triggers the bulk send)
    /setvars     - Preview/set template variables for the next send
                   Usage: /setvars var1 var2 ...
    /status      - Check the rate-limiter status
"""

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bird_api import BirdAPIClient, BirdAPIError
from contact_parser import parse_contacts_file, ContactParseError
from logger import logger
from rate_limiter import RateLimiter

load_dotenv()

# ---------------------------------------------------------------------------
# Global state (per-process; sufficient for single-instance bots)
# ---------------------------------------------------------------------------
rate_limiter = RateLimiter()

# Per-user pending template variables stored in bot_data
TEMPLATE_VARS_KEY = "template_vars"
AWAITING_BULK_KEY = "awaiting_bulk"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_bird_client() -> BirdAPIClient:
    """Create a fresh BirdAPIClient from environment variables."""
    return BirdAPIClient()


def _get_template_config() -> tuple[str, str]:
    """Return (template_id, template_language) from environment."""
    template_id = os.environ.get("WHATSAPP_TEMPLATE_ID", "")
    template_language = os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE", "en")
    return template_id, template_language


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Welcome to the WhatsApp Messaging Bot powered by Bird.com!\n\n"
        "Use /help to see all available commands."
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "📋 *Available Commands*\n\n"
        "/send <phone> [var1] [var2] ... – Send a WhatsApp template message\n"
        "/setvars var1 var2 ... – Set default template variables\n"
        "/bulk – Upload a CSV/Excel file for bulk sending\n"
        "/status – Show current rate-limiter counters\n"
        "/help – Show this help message",
        parse_mode="Markdown",
    )


async def send_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /send command.

    Usage: /send <phone> [var1] [var2] ...
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /send <phone> [var1] [var2] ...\n"
            "Example: /send +14155552671 John 20"
        )
        return

    phone = context.args[0]
    template_vars = list(context.args[1:])

    # Fall back to stored vars if none provided
    if not template_vars:
        template_vars = context.user_data.get(TEMPLATE_VARS_KEY, [])

    template_id, template_language = _get_template_config()
    if not template_id:
        await update.message.reply_text(
            "❌ WHATSAPP_TEMPLATE_ID is not configured on the server."
        )
        return

    await update.message.reply_text(f"⏳ Sending message to {phone}…")

    client = _get_bird_client()
    try:
        await rate_limiter.acquire()
        result = await client.send_template_message(
            recipient_phone=phone,
            template_id=template_id,
            template_language=template_language,
            template_variables=template_vars or None,
        )
        msg_id = result.get("id", "unknown")
        await update.message.reply_text(
            f"✅ Message sent! ID: `{msg_id}`", parse_mode="Markdown"
        )
    except BirdAPIError as exc:
        logger.error("BirdAPIError sending to %s: %s", phone, exc)
        await update.message.reply_text(f"❌ Failed: {exc.message} (status {exc.status})")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error sending to %s", phone)
        await update.message.reply_text(f"❌ Unexpected error: {exc}")
    finally:
        await client.close()


async def setvars_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /setvars command – store default template variables for the user.

    Usage: /setvars var1 var2 ...
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /setvars var1 var2 ...\n"
            "Example: /setvars John 20OFF"
        )
        return

    context.user_data[TEMPLATE_VARS_KEY] = list(context.args)
    await update.message.reply_text(
        f"✅ Template variables saved: {', '.join(context.args)}"
    )


async def bulk_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /bulk command – prompt user to upload a contact file."""
    context.user_data[AWAITING_BULK_KEY] = True
    await update.message.reply_text(
        "📂 Please upload a CSV or Excel (.xlsx) file with columns:\n"
        "`phone` (required), `name` (optional)\n\n"
        "I will send the configured WhatsApp template to each contact.",
        parse_mode="Markdown",
    )


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle file uploads – used for bulk contact sending."""
    if not context.user_data.get(AWAITING_BULK_KEY):
        await update.message.reply_text(
            "Send /bulk first, then upload your contact file."
        )
        return

    context.user_data[AWAITING_BULK_KEY] = False

    document: Document = update.message.document
    file_name = document.file_name or "contacts.csv"

    await update.message.reply_text(f"📥 Downloading {file_name}…")

    # Download file bytes
    tg_file = await context.bot.get_file(document.file_id)
    file_bytes = await tg_file.download_as_bytearray()

    # Parse contacts
    try:
        contacts = parse_contacts_file(file_name, bytes(file_bytes))
    except ContactParseError as exc:
        await update.message.reply_text(f"❌ Could not parse file: {exc}")
        return

    template_id, template_language = _get_template_config()
    if not template_id:
        await update.message.reply_text(
            "❌ WHATSAPP_TEMPLATE_ID is not configured on the server."
        )
        return

    template_vars = context.user_data.get(TEMPLATE_VARS_KEY, [])

    await update.message.reply_text(
        f"📤 Sending messages to {len(contacts)} contact(s)… This may take a while."
    )

    client = _get_bird_client()
    success_count = 0
    failure_count = 0

    for contact in contacts:
        # Per-contact variable substitution: if a 'name' field exists, prepend it
        vars_for_contact = list(template_vars)
        if contact.name and not vars_for_contact:
            vars_for_contact = [contact.name]

        try:
            await rate_limiter.acquire()
            await client.send_template_message(
                recipient_phone=contact.phone,
                template_id=template_id,
                template_language=template_language,
                template_variables=vars_for_contact or None,
            )
            success_count += 1
        except BirdAPIError as exc:
            logger.error("Failed to send to %s: %s", contact.phone, exc)
            failure_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error for %s", contact.phone)
            failure_count += 1

    await client.close()
    await update.message.reply_text(
        f"✅ Bulk send complete!\n"
        f"  • Sent: {success_count}\n"
        f"  • Failed: {failure_count}"
    )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command – show rate-limiter counters."""
    await update.message.reply_text(
        f"📊 *Rate Limiter Status*\n"
        f"  Messages in last second: {rate_limiter.current_second_count} "
        f"/ {rate_limiter.messages_per_second}\n"
        f"  Messages in last minute: {rate_limiter.current_minute_count} "
        f"/ {rate_limiter.messages_per_minute}",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Telegram bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("send", send_handler))
    application.add_handler(CommandHandler("setvars", setvars_handler))
    application.add_handler(CommandHandler("bulk", bulk_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(
        MessageHandler(filters.Document.ALL, document_handler)
    )

    logger.info("Bot is starting…")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
