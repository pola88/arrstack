import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.sonarr import SonarrClient
from ..db.models import log_request

logger = logging.getLogger(__name__)
sonarr = SonarrClient()

PAGE_SIZE = 5

MONITOR_OPTIONS = [
    ("🕐 Solo nuevos",      "future",  "Solo episodios que aún no han salido"),
    ("📦 Todo",             "all",     "Todas las temporadas completas"),
    ("📺 Última temporada", "latest",  "Solo la temporada más reciente"),
    ("❌ Sin descargas",    "none",    "Añadir sin descargar nada"),
]


def _build_results_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    count = min(PAGE_SIZE, total - page * PAGE_SIZE)
    select_row = [
        InlineKeyboardButton(str(i + 1), callback_data=f"series_pick:{page}:{i}")
        for i in range(count)
    ]
    rows = [select_row]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"series_page:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"series_page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🚫 Cancelar búsqueda", callback_data="series_cancel_search")])

    return InlineKeyboardMarkup(rows)


def _build_results_text(results: list, page: int) -> str:
    start = page * PAGE_SIZE
    lines = [f"*📺 Resultados ({len(results)} encontrados) — pág. {page + 1}:*\n"]
    for i, s in enumerate(results[start:start + PAGE_SIZE], 1):
        title = s.get("title", "?")
        year = s.get("year", "?")
        seasons = len([x for x in s.get("seasons", []) if x.get("seasonNumber", 0) > 0])
        lines.append(f"*{i}.* {title} ({year}) — {seasons} temp.")
    lines.append("\n_Tocá el número para ver detalles y confirmar._")
    return "\n".join(lines)


async def _send_results_page(chat_id: int, context, results: list, page: int):
    # start = page * PAGE_SIZE
    # page_results = results[start:start + PAGE_SIZE]

    # media_group = []
    # for i, s in enumerate(page_results):
    #     poster = s.get("remotePoster")
    #     if poster:
    #         caption = f"{i + 1}. {s.get('title', '?')} ({s.get('year', '?')})"
    #         media_group.append(InputMediaPhoto(media=poster, caption=caption))

    # if media_group:
    #     await context.bot.send_media_group(chat_id=chat_id, media=media_group)

    await context.bot.send_message(
        chat_id=chat_id,
        text=_build_results_text(results, page),
        parse_mode="Markdown",
        reply_markup=_build_results_keyboard(page, len(results)),
    )


@restricted
async def series_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "Uso: /series <título>\nEjemplo: /series Severance"
        )
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{query}*...", parse_mode="Markdown")

    try:
        results = await sonarr.search_series(query)
    except Exception as e:
        await msg.edit_text(f"❌ Error en Sonarr: {e}")
        return

    if not results:
        await msg.edit_text("No se encontraron resultados.")
        return

    user_id = update.effective_user.id
    context.bot_data[f"series_search_{user_id}"] = results
    context.bot_data[f"series_page_{user_id}"] = 0

    await msg.delete()
    await _send_results_page(update.effective_chat.id, context, results, page=0)


async def series_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    results = context.bot_data.get(f"series_search_{user_id}", [])

    # ── Cancelar búsqueda desde el listado ────────────────────────────────────
    if data == "series_cancel_search":
        await query.edit_message_text("OK, búsqueda cancelada.")
        context.bot_data.pop(f"series_search_{user_id}", None)
        context.bot_data.pop(f"series_page_{user_id}", None)
        return

    # ── Cambiar página ────────────────────────────────────────────────────────
    if data.startswith("series_page:"):
        if not results:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /series de nuevo.")
            return
        page = int(data.split(":")[1])
        context.bot_data[f"series_page_{user_id}"] = page
        await query.delete_message()
        await _send_results_page(query.message.chat_id, context, results, page)
        return

    # ── Elegir resultado → póster + opciones de monitor ───────────────────────
    if not data.startswith("series_pick:"):
        return

    _, page, idx = data.split(":")
    page, idx = int(page), int(idx)

    if not results:
        await query.edit_message_text("⏰ Sesión expirada. Ejecutá /series de nuevo.")
        return

    series = results[page * PAGE_SIZE + idx]
    context.bot_data[f"series_selected_{user_id}"] = series

    title = series.get("title", "?")
    year = series.get("year", "?")
    overview = series.get("overview", "Sin descripción disponible.")
    if len(overview) > 250:
        overview = overview[:250] + "..."
    seasons = [s for s in series.get("seasons", []) if s.get("seasonNumber", 0) > 0]
    season_count = len(seasons)
    poster_url = series.get("remotePoster")

    caption = (
        f"*{title} ({year})*\n"
        f"🗂 {season_count} temporada(s)\n"
        f"_{overview}_\n\n"
        f"*¿Qué querés descargar?*"
    )

    # Opciones de monitor + botón cancelar
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"series_monitor:{monitor}")]
         for label, monitor, _ in MONITOR_OPTIONS]
        + [[InlineKeyboardButton("🚫 Cancelar", callback_data="series_monitor:cancel")]]
    )

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

    # ── Cancelar desde la tarjeta de detalles ─────────────────────────────────
    if monitor_mode == "cancel":
        await query.edit_message_caption("OK, cancelado.")
        context.bot_data.pop(f"series_search_{user_id}", None)
        context.bot_data.pop(f"series_selected_{user_id}", None)
        context.bot_data.pop(f"series_page_{user_id}", None)
        return

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
    context.bot_data.pop(f"series_page_{user_id}", None)