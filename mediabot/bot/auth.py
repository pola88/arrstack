from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from .config import settings
import logging

logger = logging.getLogger(__name__)


def restricted(func):
    """Decorator: block non-whitelisted Telegram users."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None or user.id not in settings.allowed_user_ids:
            uid = user.id if user else "unknown"
            logger.warning(f"Unauthorized access attempt by user_id={uid}")
            if update.message:
                await update.message.reply_text("⛔ No autorizado.")
            return
        return await func(update, context)

    return wrapper
