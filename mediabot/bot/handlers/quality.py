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
async def quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /quality movie <título>   — cambiar perfil de una película
    /quality series <título>  — cambiar perfil de una serie
    """
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "*🎚 Cambiar perfil de calidad*\n\n"
            "Uso:\n"
            "  /quality movie `<título>`\n"
            "  /quality series `<título>`\n\n"
            "Ejemplo:\n"
            "  /quality movie Dune\n"
            "  /quality series Severance",
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
            profiles = await radarr.get_quality_profiles()
        else:
            all_items = await sonarr.get_all_series()
            profiles = await sonarr.get_quality_profiles()
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{e}`", parse_mode="Markdown")
        return

    match = next(
        (item for item in all_items if name in item.get("title", "").lower()), None
    )

    if not match:
        await msg.edit_text(
            f"❌ No encontré ningún *{media_type}* con ese nombre en tu biblioteca.",
            parse_mode="Markdown",
        )
        return

    title = match.get("title", "?")
    year = match.get("year", "")
    current_id = match.get("qualityProfileId", 0)
    current_name = next((p["name"] for p in profiles if p["id"] == current_id), "?")

    # Cache for callback
    context.bot_data[f"quality_{update.effective_user.id}"] = {
        "media_type": media_type,
        "item_id": match["id"],
        "title": title,
        "item": match,
    }

    keyboard = [
        [InlineKeyboardButton(
            f"{'✅ ' if p['id'] == current_id else ''}{p['name']}",
            callback_data=f"quality_set:{p['id']}:{p['name']}",
        )]
        for p in profiles
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="quality_cancel")])

    label = f"*{title} ({year})*" if year else f"*{title}*"
    await msg.edit_text(
        f"{label}\nPerfil actual: `{current_name}`\n\n*Seleccioná el nuevo perfil:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "quality_cancel":
        await query.edit_message_text("OK, sin cambios.")
        return

    _, profile_id, profile_name = data.split(":", 2)
    user_id = query.from_user.id
    cached = context.bot_data.get(f"quality_{user_id}")

    if not cached:
        await query.edit_message_text("⏰ Sesión expirada. Ejecutá el comando de nuevo.")
        return

    media_type = cached["media_type"]
    item_id = cached["item_id"]
    title = cached["title"]
    item = cached["item"]

    await query.edit_message_text(
        f"⏳ Actualizando *{title}* → `{profile_name}`...", parse_mode="Markdown"
    )

    try:
        item["qualityProfileId"] = int(profile_id)
        if media_type == "movie":
            await radarr.update_movie(item_id, item)
        else:
            await sonarr.update_series(item_id, item)

        await query.edit_message_text(
            f"✅ *{title}* — perfil actualizado a `{profile_name}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error al actualizar: {e}")

    context.bot_data.pop(f"quality_{user_id}", None)
