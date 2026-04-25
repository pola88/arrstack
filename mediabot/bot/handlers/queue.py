import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.radarr import RadarrClient
from ..services.sonarr import SonarrClient

logger = logging.getLogger(__name__)
radarr = RadarrClient()
sonarr = SonarrClient()


@restricted
async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /queue          — ver cola con botones de acción
    /queue remove   — menú para cancelar una descarga
    /queue retry    — reintentar todos los fallidos
    """
    args = context.args
    action = args[0].lower() if args else "list"

    if action == "remove":
        msg = await update.message.reply_text("🗑 Cargando cola...")
        await _show_remove_menu(msg, edit=True)
    elif action == "retry":
        msg = await update.message.reply_text("🔄 Reintentando fallidos...")
        retried = await _do_retry_failed()
        await msg.edit_text(
            "✅ No hay descargas fallidas." if retried == 0
            else f"🔄 Se reintentaron *{retried}* descarga(s) fallida(s).",
            parse_mode="Markdown",
        )
    else:
        await _show_queue_list(update)


async def _show_queue_list(update: Update):
    msg = await update.message.reply_text("📋 Cargando cola...")
    lines = ["*📋 Cola de descargas*\n"]
    has_failed = False

    try:
        rq = await radarr.get_queue()
        lines.append(f"*🎬 Radarr ({len(rq)}):*")
        if rq:
            for item in rq[:6]:
                icon, line, failed = _format_queue_item_movie(item)
                lines.append(line)
                if failed:
                    has_failed = True
        else:
            lines.append("  Vacía")
    except Exception as e:
        lines.append(f"  ❌ Error: `{e}`")

    try:
        sq = await sonarr.get_queue()
        lines.append(f"\n*📺 Sonarr ({len(sq)}):*")
        if sq:
            for item in sq[:6]:
                icon, line, failed = _format_queue_item_episode(item)
                lines.append(line)
                if failed:
                    has_failed = True
        else:
            lines.append("  Vacía")
    except Exception as e:
        lines.append(f"  ❌ Error: `{e}`")

    keyboard = [
        [InlineKeyboardButton("🗑 Cancelar una descarga", callback_data="queue_remove_menu")]
    ]
    if has_failed:
        keyboard.append(
            [InlineKeyboardButton("🔄 Reintentar fallidos", callback_data="queue_retry_all")]
        )

    await msg.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _format_queue_item_movie(item: dict):
    title = item.get("title", "?")[:40]
    status = item.get("status", "?")
    tracked = item.get("trackedDownloadStatus", "")
    size = item.get("size", 1)
    sizeleft = item.get("sizeleft", 0)
    pct = round((1 - sizeleft / max(size, 1)) * 100)
    failed = tracked == "warning" or status == "failed"
    icon = "❌" if failed else "⬇️"
    return icon, f"  {icon} `{title}` — {pct}% [{status}]", failed


def _format_queue_item_episode(item: dict):
    series = item.get("series", {}).get("title", "?")
    ep = item.get("episode", {})
    ep_code = f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}"
    status = item.get("status", "?")
    tracked = item.get("trackedDownloadStatus", "")
    size = item.get("size", 1)
    sizeleft = item.get("sizeleft", 0)
    pct = round((1 - sizeleft / max(size, 1)) * 100)
    failed = tracked == "warning" or status == "failed"
    icon = "❌" if failed else "⬇️"
    return icon, f"  {icon} `{series}` {ep_code} — {pct}% [{status}]", failed


async def _show_remove_menu(message, edit: bool = False):
    all_items = []

    try:
        for item in await radarr.get_queue():
            all_items.append({
                "id": item["id"],
                "label": f"🎬 {item.get('title', '?')[:38]}",
                "source": "radarr",
            })
    except Exception:
        pass

    try:
        for item in await sonarr.get_queue():
            series = item.get("series", {}).get("title", "?")
            ep = item.get("episode", {})
            ep_code = f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}"
            all_items.append({
                "id": item["id"],
                "label": f"📺 {series[:30]} {ep_code}",
                "source": "sonarr",
            })
    except Exception:
        pass

    if not all_items:
        text = "✅ La cola está vacía, nada que cancelar."
        if edit:
            await message.edit_text(text)
        else:
            await message.reply_text(text)
        return

    keyboard = [
        [InlineKeyboardButton(
            f"🗑 {item['label']}",
            callback_data=f"queue_del:{item['source']}:{item['id']}"
        )]
        for item in all_items[:10]
    ]
    keyboard.append([InlineKeyboardButton("← Volver", callback_data="queue_cancel")])

    markup = InlineKeyboardMarkup(keyboard)
    text = "*🗑 ¿Qué descarga querés cancelar?*"
    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def _do_retry_failed() -> int:
    retried = 0
    try:
        for item in await radarr.get_queue():
            if item.get("trackedDownloadStatus") == "warning" or item.get("status") == "failed":
                await radarr.retry_queue_item(item["id"])
                retried += 1
    except Exception as e:
        logger.error(f"Radarr retry error: {e}")

    try:
        for item in await sonarr.get_queue():
            if item.get("trackedDownloadStatus") == "warning" or item.get("status") == "failed":
                await sonarr.retry_queue_item(item["id"])
                retried += 1
    except Exception as e:
        logger.error(f"Sonarr retry error: {e}")

    return retried


# ── Callbacks ─────────────────────────────────────────────────────────────────

async def queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "queue_remove_menu":
        await _show_remove_menu(query.message, edit=True)

    elif data == "queue_retry_all":
        await query.edit_message_text("🔄 Reintentando fallidos...")
        retried = await _do_retry_failed()
        await query.edit_message_text(
            "✅ No hay descargas fallidas." if retried == 0
            else f"🔄 Se reintentaron *{retried}* descarga(s).",
            parse_mode="Markdown",
        )

    elif data.startswith("queue_del:"):
        _, source, item_id = data.split(":")
        await query.edit_message_text("🗑 Cancelando descarga...")
        try:
            if source == "radarr":
                await radarr.delete_queue_item(int(item_id))
            else:
                await sonarr.delete_queue_item(int(item_id))
            await query.edit_message_text("✅ Descarga cancelada y eliminada de la cola.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error al cancelar: {e}")

    elif data == "queue_cancel":
        await query.edit_message_text("OK.")
