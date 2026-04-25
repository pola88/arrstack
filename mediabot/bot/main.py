import logging
import asyncio
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from .config import settings
from .db.models import init_db

from .handlers.movie import movie_command, movie_callback
from .handlers.series import series_command, series_pick_callback, series_monitor_callback
from .handlers.status import status_command, wanted_command
from .handlers.subtitles import subtitles_command
from .handlers.search import search_command
from .handlers.monitor import monitor_command
from .handlers.help import help_command
from .handlers.history import history_command
from .handlers.queue import queue_command, queue_callback
from .handlers.quality import quality_command, quality_callback
from .handlers.plex import plex_command

from .notifications.dispatcher import NotificationDispatcher
from .notifications.webhook_server import WebhookServer
from .notifications.poller import poll_loop

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)


async def post_init(application):
    """
    Called by PTB after the event loop is running.
    Safe place to start aiohttp server and background tasks.
    """
    await init_db()

    dispatcher = NotificationDispatcher(
        bot=application.bot,
        chat_ids=list(settings.allowed_user_ids),
    )
    application.bot_data["dispatcher"] = dispatcher

    webhook_server = WebhookServer(
        dispatcher=dispatcher,
        host=settings.webhook_host,
        port=settings.webhook_port,
    )
    await webhook_server.start()
    logger.info(f"Webhook server started on port {settings.webhook_port}")

    asyncio.create_task(poll_loop(dispatcher, interval=300))
    logger.info("Background poller started")

    await application.bot.set_my_commands([
        BotCommand("movie",     "Buscar y añadir película"),
        BotCommand("series",    "Buscar y añadir serie"),
        BotCommand("search",    "Búsqueda unificada Radarr + Sonarr"),
        BotCommand("status",    "Estado del stack"),
        BotCommand("wanted",    "Pendientes de descarga"),
        BotCommand("queue",     "Ver cola y cancelar descargas"),
        BotCommand("history",   "Historial reciente"),
        BotCommand("quality",   "Cambiar perfil de calidad"),
        BotCommand("monitor",   "Gestionar monitoreo de series"),
        BotCommand("subtitles", "Subtítulos pendientes"),
        BotCommand("plex",      "Buscar en tu biblioteca Plex"),
        BotCommand("help",      "Lista de comandos"),
    ])
    logger.info("Bot commands registered in Telegram menu")


def build_app():
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",     help_command))
    app.add_handler(CommandHandler("help",      help_command))
    app.add_handler(CommandHandler("movie",     movie_command))
    app.add_handler(CommandHandler("series",    series_command))
    app.add_handler(CommandHandler("search",    search_command))
    app.add_handler(CommandHandler("status",    status_command))
    app.add_handler(CommandHandler("wanted",    wanted_command))
    app.add_handler(CommandHandler("queue",     queue_command))
    app.add_handler(CommandHandler("history",   history_command))
    app.add_handler(CommandHandler("quality",   quality_command))
    app.add_handler(CommandHandler("monitor",   monitor_command))
    app.add_handler(CommandHandler("subtitles", subtitles_command))
    app.add_handler(CommandHandler("plex",      plex_command))

    app.add_handler(CallbackQueryHandler(movie_callback,          pattern="^addmovie:"))
    app.add_handler(CallbackQueryHandler(series_pick_callback,    pattern="^series_pick:"))
    app.add_handler(CallbackQueryHandler(series_monitor_callback, pattern="^series_monitor:"))
    app.add_handler(CallbackQueryHandler(queue_callback,          pattern="^queue_"))
    app.add_handler(CallbackQueryHandler(quality_callback,        pattern="^quality_"))

    return app


def main():
    app = build_app()
    logger.info("Starting bot (long polling)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
