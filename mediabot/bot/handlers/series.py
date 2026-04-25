import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.sonarr import SonarrClient
from ..db.models import log_request

logger = logging.getLogger(__name__)
sonarr = SonarrClient()

MONITOR_OPTIONS = [
    ("🕐 Solo nuevos",      "future",  "Solo episodios que aún no han salido"),
    ("📦 Todo",             "all",     "Todas las temporadas completas"),
    ("📺 Última temporada", "latest",  "Solo la temporada más reciente"),
    ("❌ Sin descargas",    "none",    "Añadir sin descargar nada"),
]


@restricted
async def series_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "Uso: /series <título>\nEjemplo: /series Severance"
        )
        return

    await update.message.reply_text(f"🔍 Buscando *{query}*...", parse_mode="Markdown")

    try:
        results = await sonarr.search_series(query)
    except Exception as e:
        await update.message.reply_text(f"❌ Error en Sonarr: {e}")
        return

    if not results:
        await update.message.reply_text("No se encontraron resultados.")
        return

    top = results[:5]
    context.bot_data[f"series_search_{update.effective_user.id}"] = top

    keyboard = [
        [InlineKeyboardButton(
            f"{s.get('title', '?')} ({s.get('year', '?')})",
            callback_data=f"series_pick:{s.get('tvdbId', 0)}:{i}",
        )]
        for i, s in enumerate(top)
    ]

    await update.message.reply_text(
        f"Encontré *{len(results)}* resultado(s). ¿Cuál querés añadir?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def series_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, tvdb_id, idx = query.data.split(":")
    user_id = query.from_user.id
    cached = context.bot_data.get(f"series_search_{user_id}", [])

    if not cached:
        await query.edit_message_text("⏰ Sesión expirada. Ejecutá /series de nuevo.")
        return

    series = cached[int(idx)]
    context.bot_data[f"series_selected_{user_id}"] = series

    title = series.get("title", "?")
    year = series.get("year", "?")
    overview = series.get("overview", "Sin descripción disponible.")
    if len(overview) > 250:
        overview = overview[:250] + "..."
    seasons = [s for s in series.get("seasons", []) if s.get("seasonNumber", 0) > 0]
    season_count = len(seasons)
    poster_url = series.get("remotePoster")  # URL pública de TVDB

    caption = (
        f"*{title} ({year})*\n"
        f"🗂 {season_count} temporada(s)\n"
        f"_{overview}_\n\n"
        f"*¿Qué querés descargar?*"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"series_monitor:{monitor}")]
        for label, monitor, _ in MONITOR_OPTIONS
    ])

    # Borrar mensaje anterior y enviar póster con opciones de monitor
    await query.delete_message()

    if poster_url:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=poster_url,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=caption,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def series_monitor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    monitor_mode = query.data.split(":")[1]
    user_id = query.from_user.id
    series = context.bot_data.get(f"series_selected_{user_id}")

    if not series:
        await query.edit_message_caption("⏰ Sesión expirada. Ejecutá /series de nuevo.")
        return

    label = next((lbl for lbl, m, _ in MONITOR_OPTIONS if m == monitor_mode), monitor_mode)
    description = next((desc for _, m, desc in MONITOR_OPTIONS if m == monitor_mode), "")
    title = series.get("title", "?")
    year = series.get("year", "?")
    tvdb_id = series.get("tvdbId", 0)

    await query.edit_message_caption(
        f"⏳ Añadiendo *{title}* con modo *{label}*...",
        parse_mode="Markdown",
    )

    try:
        await sonarr.add_series(tvdb_id=tvdb_id, title=title, monitor=monitor_mode)
        await log_request(user_id, "series", title, tvdb_id)
        await query.edit_message_caption(
            f"✅ *{title} ({year})* añadida a Sonarr\n"
            f"📋 Modo: *{label}* — {description}",
            parse_mode="Markdown",
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            await query.edit_message_caption(
                f"ℹ️ *{title}* ya está en Sonarr.", parse_mode="Markdown"
            )
        else:
            await query.edit_message_caption(f"❌ Error al añadir: {e}")

    context.bot_data.pop(f"series_search_{user_id}", None)
    context.bot_data.pop(f"series_selected_{user_id}", None)