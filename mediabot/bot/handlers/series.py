import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


def _results_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    count = min(PAGE_SIZE, total - page * PAGE_SIZE)
    rows = []

    rows.append([
        InlineKeyboardButton(str(i + 1), callback_data=f"sv_pick:{page}:{i}")
        for i in range(count)
    ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"sv_page:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"sv_page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🚫 Cancelar", callback_data="sv_cancel")])
    return InlineKeyboardMarkup(rows)


def _results_text(results: list, page: int) -> str:
    start = page * PAGE_SIZE
    lines = [f"*📺 {len(results)} resultado(s) — pág. {page + 1}:*\n"]
    for i, s in enumerate(results[start:start + PAGE_SIZE], 1):
        title = s.get("title", "?")
        year = s.get("year", "?")
        seasons = len([x for x in s.get("seasons", []) if x.get("seasonNumber", 0) > 0])
        lines.append(f"*{i}.* {title} ({year}) — {seasons} temp.")
    lines.append("\n_Tocá el número para ver detalles._")
    return "\n".join(lines)


@restricted
async def series_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Uso: /series <título>\nEjemplo: /series Severance")
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
    context.bot_data[f"sv_results_{user_id}"] = results

    await msg.edit_text(
        _results_text(results, 0),
        parse_mode="Markdown",
        reply_markup=_results_keyboard(0, len(results)),
    )


async def series_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    results = context.bot_data.get(f"sv_results_{user_id}", [])

    # ── Cancelar ──────────────────────────────────────────────────────────────
    if data == "sv_cancel":
        await query.edit_message_text("OK, cancelado.")
        context.bot_data.pop(f"sv_results_{user_id}", None)
        context.bot_data.pop(f"sv_selected_{user_id}", None)
        return

    # ── Cambiar página ────────────────────────────────────────────────────────
    if data.startswith("sv_page:"):
        if not results:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /series de nuevo.")
            return
        page = int(data.split(":")[1])
        await query.edit_message_text(
            _results_text(results, page),
            parse_mode="Markdown",
            reply_markup=_results_keyboard(page, len(results)),
        )
        return

    # ── Seleccionar resultado → póster + opciones de monitor ──────────────────
    if data.startswith("sv_pick:"):
        if not results:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /series de nuevo.")
            return

        _, page, idx = data.split(":")
        series = results[int(page) * PAGE_SIZE + int(idx)]
        context.bot_data[f"sv_selected_{user_id}"] = series

        title = series.get("title", "?")
        year = series.get("year", "?")
        overview = series.get("overview", "Sin descripción disponible.")
        if len(overview) > 250:
            overview = overview[:250] + "..."
        seasons = len([s for s in series.get("seasons", []) if s.get("seasonNumber", 0) > 0])
        poster_url = series.get("remotePoster")

        caption = (
            f"*{title} ({year})*\n"
            f"🗂 {seasons} temporada(s)\n"
            f"_{overview}_\n\n"
            f"*¿Qué querés descargar?*"
        )

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(label, callback_data=f"sv_monitor:{monitor}")]
             for label, monitor, _ in MONITOR_OPTIONS]
            + [[InlineKeyboardButton("🚫 Cancelar", callback_data="sv_cancel")]]
        )

        if poster_url:
            await query.delete_message()
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=poster_url,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        else:
            await query.edit_message_text(
                caption,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )


async def series_monitor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    monitor_mode = query.data.split(":")[1]
    user_id = query.from_user.id

    # ── Cancelar desde tarjeta de detalles ────────────────────────────────────
    if monitor_mode == "cancel":
        try:
            await query.edit_message_caption("OK, cancelado.")
        except Exception:
            await query.edit_message_text("OK, cancelado.")
        context.bot_data.pop(f"sv_results_{user_id}", None)
        context.bot_data.pop(f"sv_selected_{user_id}", None)
        return

    series = context.bot_data.get(f"sv_selected_{user_id}")
    if not series:
        try:
            await query.edit_message_caption("⏰ Sesión expirada. Ejecutá /series de nuevo.")
        except Exception:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /series de nuevo.")
        return

    label = next((lbl for lbl, m, _ in MONITOR_OPTIONS if m == monitor_mode), monitor_mode)
    description = next((desc for _, m, desc in MONITOR_OPTIONS if m == monitor_mode), "")
    title = series.get("title", "?")
    year = series.get("year", "?")
    tvdb_id = series.get("tvdbId", 0)

    try:
        await query.edit_message_caption(
            f"⏳ Añadiendo *{title}* con modo *{label}*...", parse_mode="Markdown"
        )
        has_photo = True
    except Exception:
        await query.edit_message_text(
            f"⏳ Añadiendo *{title}* con modo *{label}*...", parse_mode="Markdown"
        )
        has_photo = False

    try:
        await sonarr.add_series(tvdb_id=tvdb_id, title=title, monitor=monitor_mode)
        await log_request(user_id, "series", title, tvdb_id)
        msg = (
            f"✅ *{title} ({year})* añadida a Sonarr\n"
            f"📋 Modo: *{label}* — {description}"
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            msg = f"ℹ️ *{title}* ya está en Sonarr."
        else:
            msg = f"❌ Error al añadir: {e}"

    if has_photo:
        await query.edit_message_caption(msg, parse_mode="Markdown")
    else:
        await query.edit_message_text(msg, parse_mode="Markdown")

    context.bot_data.pop(f"sv_results_{user_id}", None)
    context.bot_data.pop(f"sv_selected_{user_id}", None)