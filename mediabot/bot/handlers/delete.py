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
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /delete movie <título>  — eliminar película de Radarr
    /delete series <título> — eliminar serie de Sonarr
    """
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "*🗑 Eliminar del servidor*\n\n"
            "Uso:\n"
            "  /delete movie `<título>`\n"
            "  /delete series `<título>`\n\n"
            "Ejemplos:\n"
            "  /delete movie Dune\n"
            "  /delete series Severance\n\n"
            "⚠️ _Pedirá confirmación antes de eliminar._",
            parse_mode="Markdown",
        )
        return

    media_type = args[0].lower()
    name = " ".join(args[1:]).lower()

    if media_type not in ("movie", "series"):
        await update.message.reply_text(
            "Tipo no válido. Usa: `movie` o `series`", parse_mode="Markdown"
        )
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{name}*...", parse_mode="Markdown")

    try:
        if media_type == "movie":
            all_items = await radarr.get_all_movies()
        else:
            all_items = await sonarr.get_all_series()
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{e}`", parse_mode="Markdown")
        return

    # Buscar coincidencias (puede haber más de una)
    matches = [
        item for item in all_items
        if name in item.get("title", "").lower()
    ]

    if not matches:
        await msg.edit_text(
            f"❌ No encontré ningún *{media_type}* con ese nombre en tu biblioteca.",
            parse_mode="Markdown",
        )
        return

    # Si hay más de una coincidencia, mostrar lista para elegir
    if len(matches) > 1:
        context.bot_data[f"delete_matches_{update.effective_user.id}"] = {
            "media_type": media_type,
            "matches": matches,
        }
        keyboard = [
            [InlineKeyboardButton(
                f"{m.get('title', '?')} ({m.get('year', '?')})",
                callback_data=f"delete_pick:{i}"
            )]
            for i, m in enumerate(matches[:8])
        ]
        keyboard.append([InlineKeyboardButton("🚫 Cancelar", callback_data="delete_cancel")])
        await msg.edit_text(
            f"Encontré *{len(matches)}* coincidencias. ¿Cuál querés eliminar?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Una sola coincidencia → pedir confirmación directamente
    item = matches[0]
    await _ask_confirmation(msg, context, update.effective_user.id, media_type, item)


async def _ask_confirmation(message, context, user_id: int, media_type: str, item: dict):
    title = item.get("title", "?")
    year = item.get("year", "?")

    context.bot_data[f"delete_pending_{user_id}"] = {
        "media_type": media_type,
        "item_id": item["id"],
        "title": title,
        "year": year,
    }

    label = "película" if media_type == "movie" else "serie"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Sí, eliminar",  callback_data="delete_confirm:keep"),
        InlineKeyboardButton("🗑+🚫 Y blacklist", callback_data="delete_confirm:blacklist"),
    ], [
        InlineKeyboardButton("🚫 Cancelar",      callback_data="delete_cancel"),
    ]])

    await message.edit_text(
        f"⚠️ *¿Eliminar {label}?*\n\n"
        f"*{title} ({year})*\n\n"
        f"• *Eliminar* — quita de Radarr/Sonarr pero mantiene el archivo en disco\n"
        f"• *Eliminar + blacklist* — quita y no vuelve a descargar automáticamente\n\n"
        f"_Los archivos en /data no se borran en ningún caso._",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # ── Cancelar ──────────────────────────────────────────────────────────────
    if data == "delete_cancel":
        await query.edit_message_text("OK, cancelado. No se eliminó nada.")
        _cleanup(context, user_id)
        return

    # ── Elegir entre múltiples coincidencias ──────────────────────────────────
    if data.startswith("delete_pick:"):
        idx = int(data.split(":")[1])
        cached = context.bot_data.get(f"delete_matches_{user_id}", {})
        matches = cached.get("matches", [])
        media_type = cached.get("media_type", "movie")

        if not matches or idx >= len(matches):
            await query.edit_message_text("⏰ Sesión expirada.")
            return

        item = matches[idx]
        await _ask_confirmation(query.message, context, user_id, media_type, item)
        return

    # ── Confirmar eliminación ─────────────────────────────────────────────────
    if data.startswith("delete_confirm:"):
        blacklist = data.split(":")[1] == "blacklist"
        pending = context.bot_data.get(f"delete_pending_{user_id}")

        if not pending:
            await query.edit_message_text("⏰ Sesión expirada.")
            return

        media_type = pending["media_type"]
        item_id = pending["item_id"]
        title = pending["title"]
        year = pending["year"]

        await query.edit_message_text(f"⏳ Eliminando *{title}*...", parse_mode="Markdown")

        try:
            if media_type == "movie":
                await radarr.delete_movie(item_id, blacklist=blacklist)
            else:
                await sonarr.delete_series(item_id, blacklist=blacklist)

            blacklist_note = " (añadida a blacklist)" if blacklist else ""
            await query.edit_message_text(
                f"✅ *{title} ({year})* eliminado de "
                f"{'Radarr' if media_type == 'movie' else 'Sonarr'}{blacklist_note}.\n\n"
                f"_Los archivos en disco no fueron borrados._",
                parse_mode="Markdown",
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error al eliminar: `{e}`", parse_mode="Markdown")

        _cleanup(context, user_id)


def _cleanup(context, user_id: int):
    context.bot_data.pop(f"delete_pending_{user_id}", None)
    context.bot_data.pop(f"delete_matches_{user_id}", None)