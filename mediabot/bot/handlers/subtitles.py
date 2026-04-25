import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.bazarr import BazarrClient

logger = logging.getLogger(__name__)
bazarr = BazarrClient()


@restricted
async def subtitles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Buscando subtítulos pendientes...")
    lines = ["*🔤 Subtítulos pendientes*\n"]

    try:
        wanted_movies = await bazarr.get_wanted_movies()
        lines.append(f"*🎬 Películas sin subtítulos ({len(wanted_movies)}):*")
        for m in wanted_movies[:8]:
            lines.append(f"  • {m.get('title', '?')} ({m.get('year', '?')})")
        if not wanted_movies:
            lines.append("  Ninguna")
    except Exception as e:
        lines.append(f"*🎬 Error Bazarr:* `{e}`")

    try:
        wanted_eps = await bazarr.get_wanted_episodes()
        lines.append(f"\n*📺 Episodios sin subtítulos ({len(wanted_eps)}):*")
        for ep in wanted_eps[:8]:
            lines.append(f"  • {ep.get('seriesTitle', '?')} — {ep.get('episode_number', '?')}")
        if not wanted_eps:
            lines.append("  Ninguno")
    except Exception as e:
        lines.append(f"\n*📺 Error Bazarr:* `{e}`")

    lines.append("\n_Bazarr busca subtítulos automáticamente según su configuración._")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")
