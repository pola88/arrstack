import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.radarr import RadarrClient
from ..db.models import log_request

logger = logging.getLogger(__name__)
radarr = RadarrClient()


@restricted
async def movie_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "Uso: /movie <título>\nEjemplo: /movie Dune Part Two"
        )
        return

    await update.message.reply_text(f"🔍 Buscando *{query}*...", parse_mode="Markdown")

    try:
        results = await radarr.search_movie(query)
    except Exception as e:
        await update.message.reply_text(f"❌ Error en Radarr: {e}")
        return

    if not results:
        await update.message.reply_text("No se encontraron resultados.")
        return

    top = results[:5]
    context.bot_data[f"movie_search_{update.effective_user.id}"] = top

    keyboard = [
        [InlineKeyboardButton(
            f"{m.get('title', '?')} ({m.get('year', '?')})",
            callback_data=f"addmovie:{m.get('tmdbId', 0)}:{i}",
        )]
        for i, m in enumerate(top)
    ]

    await update.message.reply_text(
        f"Encontré *{len(results)}* resultado(s). ¿Cuál querés añadir?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # ── Elegir resultado → mostrar póster + tarjeta de confirmación ───────────
    if data.startswith("addmovie:") and "confirm" not in data and data != "addmovie_cancel":
        parts = data.split(":")
        tmdb_id = int(parts[1])
        idx = int(parts[2])

        cached = context.bot_data.get(f"movie_search_{user_id}", [])
        if not cached:
            await query.edit_message_text("⏰ Sesión expirada. Ejecutá /movie de nuevo.")
            return

        movie = cached[idx]
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
            "tmdb_id": tmdb_id, "title": title, "year": year
        }

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Añadir",   callback_data=f"addmovie_confirm:{tmdb_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="addmovie_cancel"),
        ]])

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

    # ── Confirmar → añadir a Radarr ───────────────────────────────────────────
    elif data.startswith("addmovie_confirm:"):
        tmdb_id = int(data.split(":")[1])
        cached = context.bot_data.get(f"movie_confirm_{user_id}", {})
        title = cached.get("title", "?")
        year = cached.get("year", 0)

        await query.edit_message_caption("⏳ Añadiendo...")

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

    # ── Cancelar ──────────────────────────────────────────────────────────────
    elif data == "addmovie_cancel":
        await query.edit_message_caption("OK, cancelado.")
        context.bot_data.pop(f"movie_search_{user_id}", None)
        context.bot_data.pop(f"movie_confirm_{user_id}", None)