import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.sonarr import SonarrClient

logger = logging.getLogger(__name__)
sonarr = SonarrClient()


@restricted
async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /monitor <continue|pause> [series name]
    /monitor continue Severance   → enable monitoring
    /monitor pause Severance      → disable monitoring
    /monitor list                 → show all series and their monitor status
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso:\n"
            "  /monitor list — ver todas las series\n"
            "  /monitor continue <serie> — activar monitoreo\n"
            "  /monitor pause <serie> — pausar monitoreo"
        )
        return

    action = args[0].lower()

    # ── List ──────────────────────────────────────────────────────────────────
    if action == "list":
        msg = await update.message.reply_text("📋 Cargando series...")
        try:
            all_series = await sonarr.get_all_series()
            if not all_series:
                await msg.edit_text("No hay series en Sonarr.")
                return

            lines = ["*📺 Series en Sonarr:*\n"]
            for s in sorted(all_series, key=lambda x: x.get("title", "")):
                monitored = s.get("monitored", False)
                icon = "✅" if monitored else "⏸"
                lines.append(f"  {icon} {s.get('title', '?')} ({s.get('year', '?')})")

            await msg.edit_text("\n".join(lines), parse_mode="Markdown")
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}")
        return

    # ── Continue / Pause ─────────────────────────────────────────────────────
    if action not in ("continue", "pause"):
        await update.message.reply_text("Acción no válida. Usa: continue, pause, list")
        return

    if len(args) < 2:
        await update.message.reply_text(f"Uso: /monitor {action} <nombre de la serie>")
        return

    series_name = " ".join(args[1:]).lower()
    monitored = action == "continue"
    msg = await update.message.reply_text(f"⏳ Buscando *{series_name}*...", parse_mode="Markdown")

    try:
        all_series = await sonarr.get_all_series()
        match = next(
            (s for s in all_series if series_name in s.get("title", "").lower()),
            None,
        )
        if not match:
            await msg.edit_text(f"❌ No encontré ninguna serie con *{series_name}*.", parse_mode="Markdown")
            return

        await sonarr.set_monitor(match["id"], monitored)
        state = "activado ✅" if monitored else "pausado ⏸"
        await msg.edit_text(
            f"*{match['title']}* — monitoreo {state}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")
