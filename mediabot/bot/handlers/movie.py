import logging
from typing import Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.radarr import RadarrClient
from ..db.models import log_request

logger = logging.getLogger(__name__)
radarr = RadarrClient()

PAGE_SIZE = 5


def _results_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    count = min(PAGE_SIZE, total - page * PAGE_SIZE)
    rows = []

    # Fila de números
    rows.append([
        InlineKeyboardButton(str(i + 1), callback_data=f"mv_pick:{page}:{i}")
        for i in range(count)
    ])

    # Navegación
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"mv_page:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"mv_page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🚫 Cancelar", callback_data="mv_cancel")])
    return InlineKeyboardMarkup(rows)


def _results_text(results: list, page: int) -> str:
    start = page * PAGE_SIZE
    lines = [f"*🎬 {len(results)} resultado(s) — pág. {page + 1}:*\n"]
    for i, m in enumerate(results[start:start + PAGE_SIZE], 1):
        title = m.get("title", "?")
        year = m.get("year", "?")
        lines.append(f"*{i}.* {title} ({year})")
    lines.append("\n_Tocá el número para ver detalles._")
    return "\n".join(lines)


def _format_genres(genres_raw: Any) -> str:
    if isinstance(genres_raw, str):
        return genres_raw.strip()
    if not isinstance(genres_raw, list):
        return ""

    names: list[str] = []
    for item in genres_raw[:3]:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        else:
            name = ""
        if name:
            names.append(name)
    return ", ".join(names)


def _extract_imdb_rating(movie: dict[str, Any]) -> float:
    ratings = movie.get("ratings", {})
    if not isinstance(ratings, dict):
        return 0.0

    imdb = ratings.get("imdb", {})
    if not isinstance(imdb, dict):
        return 0.0

    value = imdb.get("value", 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@restricted
async def movie_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Uso: /movie <título>\nEjemplo: /movie Dune Part Two")
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{query}*...", parse_mode="Markdown")

    try:
        results = await radarr.search_movie(query)
    except Exception as e:
        await msg.edit_text(f"❌ Error en Radarr: {e}")
        return

    if not results:
        await msg.edit_text("No se encontraron resultados.")
        return

    user_id = update.effective_user.id
    context.bot_data[f"mv_results_{user_id}"] = results

    await msg.edit_text(
        _results_text(results, 0),
        parse_mode="Markdown",
        reply_markup=_results_keyboard(0, len(results)),
    )


async def movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    results = context.bot_data.get(f"mv_results_{user_id}", [])

    # ── Cancelar ──────────────────────────────────────────────────────────────
    if data == "mv_cancel":
        await query.edit_message_text("OK, cancelado.")
        context.bot_data.pop(f"mv_results_{user_id}", None)
        context.bot_data.pop(f"mv_confirm_{user_id}", None)
        return

    # ── Cambiar página ────────────────────────────────────────────────────────
    if data.startswith("mv_page:"):
        if not results:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /movie de nuevo.")
            return
        page = int(data.split(":")[1])
        await query.edit_message_text(
            _results_text(results, page),
            parse_mode="Markdown",
            reply_markup=_results_keyboard(page, len(results)),
        )
        return

    # ── Seleccionar resultado → tarjeta de confirmación ───────────────────────
    if data.startswith("mv_pick:"):
        if not results:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /movie de nuevo.")
            return

        _, page, idx = data.split(":")
        movie = results[int(page) * PAGE_SIZE + int(idx)]

        title = movie.get("title", "?")
        year = movie.get("year", 0)
        overview = movie.get("overview", "Sin descripción.")
        if len(overview) > 250:
            overview = overview[:250] + "..."
        genres = _format_genres(movie.get("genres", []))
        runtime = movie.get("runtime", 0)
        rating = _extract_imdb_rating(movie)
        poster_url = movie.get("remotePoster")

        lines = [f"*{title} ({year})*\n"]
        if genres:
            lines.append(f"🎭 {genres}")
        if runtime:
            lines.append(f"⏱ {runtime} min")
        if rating:
            lines.append(f"⭐ {rating:.1f} IMDb")
        lines.append(f"\n_{overview}_\n")
        lines.append("*¿Confirmás la descarga?*")
        caption = "\n".join(lines)

        context.bot_data[f"mv_confirm_{user_id}"] = {
            "tmdb_id": movie.get("tmdbId", 0),
            "title": title,
            "year": year,
        }

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Añadir",   callback_data="mv_confirm"),
            InlineKeyboardButton("❌ Cancelar", callback_data="mv_cancel"),
        ]])

        if poster_url:
            # Borrar mensaje de lista y enviar foto con caption
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
        return

    # ── Confirmar → añadir ────────────────────────────────────────────────────
    if data == "mv_confirm":
        cached = context.bot_data.get(f"mv_confirm_{user_id}", {})
        title = cached.get("title", "?")
        year = cached.get("year", 0)
        tmdb_id = cached.get("tmdb_id", 0)

        # Si el mensaje tiene foto usamos edit_message_caption, si no edit_message_text
        try:
            await query.edit_message_caption("⏳ Añadiendo...", parse_mode="Markdown")
            has_photo = True
        except Exception:
            await query.edit_message_text("⏳ Añadiendo...", parse_mode="Markdown")
            has_photo = False

        try:
            await radarr.add_movie(tmdb_id=tmdb_id, title=title, year=year)
            await log_request(user_id, "movie", title, tmdb_id)
            msg = f"✅ *{title} ({year})* añadida a Radarr y en cola de descarga."
        except Exception as e:
            if "already exists" in str(e).lower():
                msg = f"ℹ️ *{title}* ya está en Radarr."
            else:
                msg = f"❌ Error al añadir: {e}"

        if has_photo:
            await query.edit_message_caption(msg, parse_mode="Markdown")
        else:
            await query.edit_message_text(msg, parse_mode="Markdown")

        context.bot_data.pop(f"mv_results_{user_id}", None)
        context.bot_data.pop(f"mv_confirm_{user_id}", None)