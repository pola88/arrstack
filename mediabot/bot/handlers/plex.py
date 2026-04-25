import logging
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from ..auth import restricted
from ..config import settings

logger = logging.getLogger(__name__)


@restricted
async def plex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /plex <título>  — buscar en tu biblioteca Plex local
    /plex           — resumen de la biblioteca
    """
    args = context.args

    if not settings.plex_token:
        await update.message.reply_text(
            "⚠️ Plex no está configurado. Añadí `PLEX_TOKEN` al `.env`.",
            parse_mode="Markdown",
        )
        return

    if not args:
        await _plex_library_summary(update)
        return

    query = " ".join(args)
    await _plex_search(update, query)


async def _plex_search(update: Update, query: str):
    msg = await update.message.reply_text(f"🔍 Buscando *{query}* en Plex...", parse_mode="Markdown")

    try:
        results = await _search_plex(query)
    except Exception as e:
        await msg.edit_text(f"❌ Error conectando con Plex: `{e}`", parse_mode="Markdown")
        return

    if not results:
        await msg.edit_text(
            f"❌ *{query}* no está en tu biblioteca Plex.\n\n"
            f"Podés añadirla con /movie o /series.",
            parse_mode="Markdown",
        )
        return

    lines = [f"*🎬 Resultados en Plex para* `{query}`:\n"]
    for item in results[:8]:
        media_type = item.get("type", "")
        title = item.get("title", "?")
        year = item.get("year", "")
        rating = item.get("rating", "")

        if media_type == "movie":
            icon = "🎬"
            extra = f"({year})" if year else ""
            rating_str = f" ⭐ {rating:.1f}" if rating else ""
            lines.append(f"  {icon} *{title}* {extra}{rating_str}")

        elif media_type == "show":
            icon = "📺"
            seasons = item.get("childCount", "?")
            lines.append(f"  {icon} *{title}* ({year}) — {seasons} temporada(s)")

        elif media_type == "episode":
            show = item.get("grandparentTitle", "?")
            season = item.get("parentIndex", 0)
            ep = item.get("index", 0)
            lines.append(f"  📺 *{show}* S{season:02d}E{ep:02d} — {title}")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


async def _plex_library_summary(update: Update):
    msg = await update.message.reply_text("📚 Cargando resumen de biblioteca...")

    try:
        sections = await _get_library_sections()
    except Exception as e:
        await msg.edit_text(f"❌ Error conectando con Plex: `{e}`", parse_mode="Markdown")
        return

    if not sections:
        await msg.edit_text("No se encontraron bibliotecas en Plex.")
        return

    lines = ["*📚 Biblioteca Plex*\n"]
    for section in sections:
        name = section.get("title", "?")
        stype = section.get("type", "?")
        count = section.get("count", "?")
        icon = "🎬" if stype == "movie" else "📺" if stype == "show" else "🎵"
        lines.append(f"  {icon} *{name}* — {count} elemento(s)")

    lines.append("\n_Usa /plex `<título>` para buscar algo específico._")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


async def _search_plex(query: str) -> list:
    url = f"{settings.plex_url}/search"
    params = {
        "query": query,
        "X-Plex-Token": settings.plex_token,
    }
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data.get("MediaContainer", {}).get("Metadata", [])


async def _get_library_sections() -> list:
    url = f"{settings.plex_url}/library/sections"
    params = {"X-Plex-Token": settings.plex_token}
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data.get("MediaContainer", {}).get("Directory", [])
