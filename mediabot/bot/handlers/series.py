import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.sonarr import SonarrClient
from ..db.models import log_request

logger = logging.getLogger(__name__)
sonarr = SonarrClient()

# (label, monitor_value, description)
MONITOR_OPTIONS = [
    ("🕐 Solo nuevos",       "future",  "Solo episodios que aún no han salido"),
    ("📦 Todo",              "all",     "Todas las temporadas completas"),
    ("📺 Última temporada",  "latest",  "Solo la temporada más reciente"),
    ("❌ Sin descargas",     "none",    "Añadir sin descargar nada"),
]


@restricted
async def series_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "Uso: /series <título>\nEjemplo: /series Severance"
        )
        return

    await update.message.reply_text(
        f"🔍 Buscando *{query}*...", parse_mode="Markdown"
    )

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
        f"Encontré *{len(results)}* resultado(s). ¿Cuál quieres añadir?",
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
        await query.edit_message_text("⏰ Sesión expirada. Ejecuta /series de nuevo.")
        return

    series = cached[int(idx)]
    context.bot_data[f"series_selected_{user_id}"] = series

    # Build info card
    overview = series.get("overview", "Sin descripción disponible.")
    if len(overview) > 200:
        overview = overview[:200] + "..."

    seasons = series.get("seasons", [])
    season_count = len([s for s in seasons if s.get("seasonNumber", 0) > 0])

    header = (
        f"📺 *{series.get('title')} ({series.get('year', '?')})*\n"
        f"🗂 {season_count} temporada(s)\n"
        f"_{overview}_\n\n"
        f"*¿Qué quieres descargar?*"
    )

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"series_monitor:{monitor}")]
        for label, monitor, _ in MONITOR_OPTIONS
    ]

    await query.edit_message_text(
        header,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def series_monitor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    monitor_mode = query.data.split(":")[1]
    user_id = query.from_user.id
    series = context.bot_data.get(f"series_selected_{user_id}")

    if not series:
        await query.edit_message_text("⏰ Sesión expirada. Ejecuta /series de nuevo.")
        return

    label = next((lbl for lbl, m, _ in MONITOR_OPTIONS if m == monitor_mode), monitor_mode)
    description = next((desc for _, m, desc in MONITOR_OPTIONS if m == monitor_mode), "")
    title = series.get("title", "?")
    year = series.get("year", "?")
    tvdb_id = series.get("tvdbId", 0)

    await query.edit_message_text(
        f"⏳ Añadiendo *{title}* con modo *{label}*...",
        parse_mode="Markdown",
    )

    try:
        await sonarr.add_series(
            tvdb_id=tvdb_id,
            title=title,
            monitor=monitor_mode,
        )
        await log_request(user_id, "series", title, tvdb_id)
        await query.edit_message_text(
            f"✅ *{title} ({year})* añadida a Sonarr\n"
            f"📋 Modo: *{label}* — {description}",
            parse_mode="Markdown",
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            await query.edit_message_text(
                f"ℹ️ *{title}* ya está en Sonarr.", parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(f"❌ Error al añadir: {e}")

    # Clean up cache
    context.bot_data.pop(f"series_search_{user_id}", None)
    context.bot_data.pop(f"series_selected_{user_id}", None)
