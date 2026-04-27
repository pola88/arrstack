import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.radarr import RadarrClient
from ..db.models import log_request

logger = logging.getLogger(__name__)
radarr = RadarrClient()

PAGE_SIZE = 5


def _build_results_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    count = min(PAGE_SIZE, total - page * PAGE_SIZE)
    select_row = [
        InlineKeyboardButton(str(i + 1), callback_data=f"addmovie_pick:{page}:{i}")
        for i in range(count)
    ]
    rows = [select_row]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"addmovie_page:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"addmovie_page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🚫 Cancelar búsqueda", callback_data="addmovie_cancel_search")])

    return InlineKeyboardMarkup(rows)


def _build_results_text(results: list, page: int) -> str:
    start = page * PAGE_SIZE
    lines = [f"*🎬 Resultados ({len(results)} encontrados) — pág. {page + 1}:*\n"]
    for i, m in enumerate(results[start:start + PAGE_SIZE], 1):
        title = m.get("title", "?")
        year = m.get("year", "?")
        lines.append(f"*{i}.* {title} ({year})")
    lines.append("\n_Tocá el número para ver detalles y confirmar._")
    return "\n".join(lines)


async def _send_results_page(chat_id: int, context, results: list, page: int):
    # start = page * PAGE_SIZE
    # page_results = results[start:start + PAGE_SIZE]

    # media_group = []
    # for i, m in enumerate(page_results):
    #     poster = m.get("remotePoster")
    #     if poster:
    #         caption = f"{i + 1}. {m.get('title', '?')} ({m.get('year', '?')})"
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
async def movie_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "Uso: /movie <título>\nEjemplo: /movie Dune Part Two"
        )
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
    context.bot_data[f"movie_search_{user_id}"] = results
    context.bot_data[f"movie_page_{user_id}"] = 0

    await msg.delete()
    await _send_results_page(update.effective_chat.id, context, results, page=0)


async def movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    results = context.bot_data.get(f"movie_search_{user_id}", [])

    # ── Cancelar desde el listado ─────────────────────────────────────────────
    if data == "addmovie_cancel_search":
        await query.edit_message_text("OK, búsqueda cancelada.")
        context.bot_data.pop(f"movie_search_{user_id}", None)
        context.bot_data.pop(f"movie_page_{user_id}", None)
        return

    # ── Cambiar página ────────────────────────────────────────────────────────
    if data.startswith("addmovie_page:"):
        if not results:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /movie de nuevo.")
            return
        page = int(data.split(":")[1])
        context.bot_data[f"movie_page_{user_id}"] = page
        await query.delete_message()
        await _send_results_page(query.message.chat_id, context, results, page)
        return

    # ── Elegir resultado → tarjeta de confirmación con póster ─────────────────
    if data.startswith("addmovie_pick:"):
        if not results:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /movie de nuevo.")
            return

        _, page, idx = data.split(":")
        page, idx = int(page), int(idx)
        movie = results[page * PAGE_SIZE + idx]

        title = movie.get("title", "?")
        year = movie.get("year", 0)
        overview = movie.get("overview", "Sin descripción.")
        if len(overview) > 250:
            overview = overview[:250] + "..."
        genres = ", ".join(g.get("name", "") for g in movie.get("genres", [])[:3])
        runtime = movie.get("runtime", 0)
        rating = movie.get("ratings", {}).get("imdb", {}).get("value", 0)
        poster_url = movie.get("remotePoster")

        caption_lines = [f"*{title} ({year})*\n"]
        if genres:
            caption_lines.append(f"🎭 {genres}")
        if runtime:
            caption_lines.append(f"⏱ {runtime} min")
        if rating:
            caption_lines.append(f"⭐ {rating:.1f} IMDb")
        caption_lines.append(f"\n_{overview}_\n")
        caption_lines.append("*¿Confirmás la descarga?*")
        caption = "\n".join(caption_lines)

        context.bot_data[f"movie_confirm_{user_id}"] = {
            "tmdb_id": movie.get("tmdbId", 0),
            "title": title,
            "year": year,
        }

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Añadir",   callback_data=f"addmovie_confirm:{movie.get('tmdbId', 0)}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="addmovie_cancel"),
            ]
        ])

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
        return

    # ── Confirmar → añadir a Radarr ───────────────────────────────────────────
    if data.startswith("addmovie_confirm:"):
        tmdb_id = int(data.split(":")[1])
        cached = context.bot_data.get(f"movie_confirm_{user_id}", {})
        title = cached.get("title", "?")
        year = cached.get("year", 0)

        await query.edit_message_caption("⏳ Añadiendo...", parse_mode="Markdown")

        try:
            await radarr.add_movie(tmdb_id=tmdb_id, title=title, year=year)
            await log_request(user_id, "movie", title, tmdb_id)
            await query.edit_message_caption(
                f"✅ *{title} ({year})* añadida a Radarr y en cola de descarga.",
                parse_mode="Markdown",
            )
        except Exception as e:
            if "already exists" in str(e).lower():
                await query.edit_message_caption(
                    f"ℹ️ *{title}* ya está en Radarr.", parse_mode="Markdown"
                )
            else:
                await query.edit_message_caption(f"❌ Error al añadir: {e}")

        context.bot_data.pop(f"movie_search_{user_id}", None)
        context.bot_data.pop(f"movie_confirm_{user_id}", None)
        context.bot_data.pop(f"movie_page_{user_id}", None)
        return

    # ── Cancelar desde la tarjeta de confirmación ─────────────────────────────
    if data == "addmovie_cancel":
        await query.edit_message_caption("OK, cancelado.")
        context.bot_data.pop(f"movie_search_{user_id}", None)
        context.bot_data.pop(f"movie_confirm_{user_id}", None)
        context.bot_data.pop(f"movie_page_{user_id}", None)