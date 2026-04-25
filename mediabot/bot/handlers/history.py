import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.radarr import RadarrClient
from ..services.sonarr import SonarrClient

logger = logging.getLogger(__name__)
radarr = RadarrClient()
sonarr = SonarrClient()

EVENT_ICONS = {
    "grabbed":               "⬇️",
    "downloadFolderImported":"✅",
    "movieFileImported":     "✅",
    "episodeFileImported":   "✅",
    "downloadFailed":        "❌",
    "downloadIgnored":       "⏭",
}


@restricted
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /history           — últimas entradas de ambos
    /history movies    — solo películas
    /history series    — solo series
    """
    args = context.args
    filter_type = args[0].lower() if args else "all"

    msg = await update.message.reply_text("📜 Cargando historial...")
    lines = ["*📜 Historial reciente*\n"]

    # ── Radarr ────────────────────────────────────────────────────────────────
    if filter_type in ("all", "movies"):
        try:
            records = await radarr.get_history(page_size=8)
            lines.append("*🎬 Películas:*")
            if records:
                for r in records:
                    event = r.get("eventType", "?")
                    title = r.get("movie", {}).get("title", "?")
                    date = r.get("date", "")[:10]
                    icon = EVENT_ICONS.get(event, "•")
                    lines.append(f"  {icon} `{date}` — {title}")
            else:
                lines.append("  Sin historial")
        except Exception as e:
            lines.append(f"  ❌ Radarr: `{e}`")

    # ── Sonarr ────────────────────────────────────────────────────────────────
    if filter_type in ("all", "series"):
        try:
            records = await sonarr.get_history(page_size=8)
            lines.append("\n*📺 Series:*")
            if records:
                for r in records:
                    event = r.get("eventType", "?")
                    series = r.get("series", {}).get("title", "?")
                    ep = r.get("episode", {})
                    ep_code = f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}"
                    date = r.get("date", "")[:10]
                    icon = EVENT_ICONS.get(event, "•")
                    lines.append(f"  {icon} `{date}` — {series} {ep_code}")
            else:
                lines.append("  Sin historial")
        except Exception as e:
            lines.append(f"  ❌ Sonarr: `{e}`")

    lines.append("\n_Filtros: /history · /history movies · /history series_")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")
