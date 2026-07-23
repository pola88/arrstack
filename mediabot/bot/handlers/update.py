import os
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
 
PORTAINER_URL = os.environ.get("PORTAINER_URL", "https://192.168.86.45:9443")
PORTAINER_API_TOKEN = os.environ.get("PORTAINER_API_TOKEN", "")
 
# Un stack por entrada: nombre -> (stack_id, endpoint_id, tipo)
# tipo: "git" o "standalone"
STACKS = {
    "arrstack": (int(os.environ.get("STACK_ID_ARR", "0")), int(os.environ.get("ENDPOINT_ID", "3")), "git"),
    "monitoring": (int(os.environ.get("STACK_ID_MONITORING", "0")), int(os.environ.get("ENDPOINT_ID", "3")), "standalone"),
}
 
 
async def update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /update <stack>\nEj: /update arrstack\n\n"
            f"Stacks conocidos: {', '.join(STACKS)}"
        )
        return
 
    stack = context.args[0].lower()
    if stack not in STACKS or not STACKS[stack][0]:
        await update.message.reply_text(f"No conozco el stack '{stack}' (o falta configurar su ID).")
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
    stack_id, endpoint_id, kind = STACKS.get(stack, (0, 0, None))
    if not stack_id:
        await query.edit_message_text(f"No conozco el stack '{stack}'.")
        return
 
    await query.edit_message_text(f"⏳ Actualizando {stack}...")
    headers = {"X-API-Key": PORTAINER_API_TOKEN}
 
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if kind == "git":
                resp = await client.put(
                    f"{PORTAINER_URL}/api/stacks/{stack_id}/git/redeploy",
                    params={"endpointId": endpoint_id},
                    headers=headers,
                    json={"PullImage": True},
                )
            else:
                # standalone: primero traer el compose actual, después reenviarlo con pull
                file_resp = await client.get(
                    f"{PORTAINER_URL}/api/stacks/{stack_id}/file",
                    params={"endpointId": endpoint_id},
                    headers=headers,
                )
                file_resp.raise_for_status()
                compose_content = file_resp.json()["StackFileContent"]
 
                resp = await client.put(
                    f"{PORTAINER_URL}/api/stacks/{stack_id}",
                    params={"endpointId": endpoint_id},
                    headers=headers,
                    json={
                        "StackFileContent": compose_content,
                        "Env": [],
                        "PullImage": True,
                        "Prune": False,
                    },
                )
 
        if resp.status_code == 200:
            await query.edit_message_text(f"✅ {stack} actualizado (pull + redeploy).")
        else:
            await query.edit_message_text(
                f"❌ Portainer devolvió {resp.status_code} al actualizar {stack}:\n{resp.text[:300]}"
            )
    except httpx.HTTPError as e:
        await query.edit_message_text(f"❌ Error al contactar Portainer: {e}")