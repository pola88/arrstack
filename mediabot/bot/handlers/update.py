import os
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
 
# Un webhook por stack en Portainer. Agregá acá los que tengas.
WEBHOOKS = {
    "arr-stack": os.environ.get("WEBHOOK_ARR_STACK", ""),
    "monitoring": os.environ.get("WEBHOOK_MONITORING", ""),
}
 
async def update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /update <stack>\nEj: /update arr-stack\n\n"
            f"Stacks conocidos: {', '.join(WEBHOOKS)}"
        )
        return
 
    stack = context.args[0].lower()
    if stack not in WEBHOOKS or not WEBHOOKS[stack]:
        await update.message.reply_text(f"No conozco el stack '{stack}' (o falta configurar su webhook).")
        return
 
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"upd_{stack}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="upd_cancel"),
    ]])
    await update.message.reply_text(
        f"¿Actualizar el stack *{stack}*? Va a hacer pull + redeploy de todos sus containers.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
 
 
async def update_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
 
    if query.data == "upd_cancel":
        await query.edit_message_text("Cancelado.")
        return
 
    stack = query.data.replace("upd_", "")
    webhook_url = WEBHOOKS.get(stack)
    if not webhook_url:
        await query.edit_message_text(f"No conozco el stack '{stack}'.")
        return
 
    await query.edit_message_text(f"⏳ Actualizando {stack}...")
 
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(webhook_url)
        if resp.status_code in (200, 204):
            await query.edit_message_text(f"✅ {stack} actualizado (pull + redeploy).")
        else:
            await query.edit_message_text(
                f"❌ Portainer devolvió {resp.status_code} al actualizar {stack}."
            )
    except httpx.HTTPError as e:
        await query.edit_message_text(f"❌ Error al contactar Portainer: {e}")