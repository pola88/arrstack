import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.radarr import RadarrClient
from ..services.sonarr import SonarrClient
import asyncio

logger = logging.getLogger(__name__)
radarr = RadarrClient()
sonarr = SonarrClient()


@restricted
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "Uso: /search <título>\nBusca en Radarr y Sonarr simultáneamente."
        )
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{query}* en Radarr y Sonarr...", parse_mode="Markdown")

    movie_results, series_results = await asyncio.gather(
        radarr.search_movie(query),
        sonarr.search_series(query),
        return_exceptions=True,
    )

    lines = [f"*🔎 Resultados para:* `{query}`\n"]

    # ── Movies ────────────────────────────────────────────────────────────────
    if isinstance(movie_results, Exception):
        lines.append(f"*🎬 Películas:* ❌ `{movie_results}`")
    elif movie_results:
        lines.append(f"*🎬 Películas ({len(movie_results)}):*")
        for m in movie_results[:5]:
            title = m.get("title", "?")
            year = m.get("year", "?")
            overview = m.get("overview", "")[:80]
            lines.append(f"  • *{title}* ({year})\n    _{overview}_")
    else:
        lines.append("*🎬 Películas:* Sin resultados")

    # ── Series ────────────────────────────────────────────────────────────────
    if isinstance(series_results, Exception):
        lines.append(f"\n*📺 Series:* ❌ `{series_results}`")
    elif series_results:
        lines.append(f"\n*📺 Series ({len(series_results)}):*")
        for s in series_results[:5]:
            title = s.get("title", "?")
            year = s.get("year", "?")
            overview = s.get("overview", "")[:80]
            lines.append(f"  • *{title}* ({year})\n    _{overview}_")
    else:
        lines.append("\n*📺 Series:* Sin resultados")

    lines.append("\n_Usa /movie o /series para añadir._")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")
