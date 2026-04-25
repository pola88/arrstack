from telegram import Update
from telegram.ext import ContextTypes
from ..auth import restricted

HELP_TEXT = """
*🤖 MediaBot — Comandos disponibles*

*🔍 Búsqueda y adición:*
/movie `<título>` — Buscar y añadir película a Radarr
/series `<título>` — Buscar y añadir serie a Sonarr
/search `<título>` — Búsqueda unificada Radarr + Sonarr

*📋 Cola y descargas:*
/queue — Ver cola con botones de acción
/queue remove — Cancelar una descarga
/queue retry — Reintentar fallidos
/history — Historial reciente
/history movies — Solo películas
/history series — Solo series

*🎚 Calidad:*
/quality movie `<título>` — Cambiar perfil de calidad
/quality series `<título>` — Cambiar perfil de calidad

*📺 Monitoreo:*
/monitor list — Ver todas las series
/monitor continue `<serie>` — Activar monitoreo
/monitor pause `<serie>` — Pausar monitoreo

*📊 Estado:*
/status — Estado del stack completo
/wanted — Pendientes de descarga

*🎬 Plex:*
/plex — Resumen de la biblioteca
/plex `<título>` — Buscar en tu biblioteca local

*🔤 Subtítulos:*
/subtitles — Ver subtítulos pendientes en Bazarr

/help — Este mensaje
"""


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")
