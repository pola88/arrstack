import logging
from telegram import Bot
from ..utils.disk import get_disk_usage
from ..config import settings

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Routes webhook events from arr services to Telegram messages."""

    def __init__(self, bot: Bot, chat_ids: list):
        self.bot = bot
        self.chat_ids = chat_ids

    async def _send(self, message: str):
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(chat_id, message, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to notify chat_id={chat_id}: {e}")

    # ── Sonarr ────────────────────────────────────────────────────────────────

    async def handle_sonarr_event(self, event: str, data: dict):
        series = data.get("series", {}).get("title", "Unknown")
        episodes = data.get("episodes", [{}])
        ep = episodes[0] if episodes else {}
        ep_code = f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}"
        ep_title = ep.get("title", "")

        release_title = data.get("release", {}).get("releaseTitle", "")

        messages = {
            "Grab": (
                f"⬇️ *{series}* {ep_code} — descarga iniciada\n"
                + (f"📦 `{release_title}`" if release_title else "")
            ),
            "Download": (
                f"✅ *{series}* {ep_code} — descarga completada"
                + (f"\n_{ep_title}_" if ep_title else "")
            ),
            "EpisodeFileImported": (
                f"🎉 *{series}* {ep_code} — ¡ya disponible en Plex!"
                + (f"\n_{ep_title}_" if ep_title else "")
            ),
            "SeriesAdd":    f"📺 Serie *{series}* añadida a Sonarr",
            "SeriesDelete": f"🗑 Serie *{series}* eliminada de Sonarr",
            "Health":       f"⚠️ *Sonarr* — problema:\n`{data.get('message', '')}`",
            "ApplicationUpdate": (
                f"🔄 *Sonarr* actualizado a "
                f"`v{data.get('updateMessage', {}).get('newVersion', '?')}`"
            ),
        }

        msg = messages.get(event)
        if msg:
            await self._send(msg)
        else:
            logger.debug(f"Unhandled Sonarr event: {event}")

    # ── Radarr ────────────────────────────────────────────────────────────────

    async def handle_radarr_event(self, event: str, data: dict):
        movie = data.get("movie", {}).get("title", "Unknown")
        year = data.get("movie", {}).get("year", "")
        label = f"*{movie} ({year})*" if year else f"*{movie}*"
        release_title = data.get("release", {}).get("releaseTitle", "")

        messages = {
            "Grab": (
                f"⬇️ {label} — descarga iniciada\n"
                + (f"📦 `{release_title}`" if release_title else "")
            ),
            "Download":          f"✅ {label} — descarga completada",
            "MovieFileImported": f"🎬 {label} — ¡ya disponible en Plex!",
            "MovieAdded":        f"🎬 {label} — añadida a Radarr",
            "MovieDelete":       f"🗑 {label} — eliminada de Radarr",
            "Health":            f"⚠️ *Radarr* — problema:\n`{data.get('message', '')}`",
            "ApplicationUpdate": (
                f"🔄 *Radarr* actualizado a "
                f"`v{data.get('updateMessage', {}).get('newVersion', '?')}`"
            ),
        }

        msg = messages.get(event)
        if msg:
            await self._send(msg)
        else:
            logger.debug(f"Unhandled Radarr event: {event}")

    # ── Plex ──────────────────────────────────────────────────────────────────

    async def handle_plex_event(self, data: dict):
        event = data.get("event", "")
        meta = data.get("Metadata", {})
        title = meta.get("title", "Unknown")
        media_type = meta.get("type", "")

        if event == "media.play":
            icon = "🎬" if media_type == "movie" else "📺"
            await self._send(f"▶️ {icon} Reproduciendo: *{title}*")

    # ── System alerts ─────────────────────────────────────────────────────────

    async def send_disk_warning(self, free_h: str, pct: float):
        """Disk low alert — includes action suggestions."""
        await self._send(
            f"⚠️ *Disco casi lleno*\n"
            f"Quedan *{free_h}* libres ({100 - pct:.1f}% disponible)\n\n"
            f"Podés revisar:\n"
            f"• /queue — ver descargas activas\n"
            f"• /status — estado completo del disco"
        )

    async def send_service_down(self, service_name: str):
        await self._send(f"🔴 *{service_name}* no responde")

    async def send_service_up(self, service_name: str):
        await self._send(f"🟢 *{service_name}* volvió a estar en línea")
