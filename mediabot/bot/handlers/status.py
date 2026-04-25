import logging
import humanize
from telegram import Update
from telegram.ext import ContextTypes
from ..auth import restricted
from ..services.radarr import RadarrClient
from ..services.sonarr import SonarrClient
from ..services.qbittorrent import QBittorrentClient
from ..services.bazarr import BazarrClient
from ..utils.disk import get_disk_usage
from ..utils.formatters import format_torrent_status, format_queue_item_radarr, format_queue_item_sonarr
from ..config import settings

logger = logging.getLogger(__name__)

radarr = RadarrClient()
sonarr = SonarrClient()
qbit = QBittorrentClient()
bazarr = BazarrClient()


@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📊 Obteniendo estado...")
    lines = ["*📡 Estado del Stack*\n"]

    # ── Active Downloads ──────────────────────────────────────────────────────
    try:
        torrents = await qbit.get_torrents("active")
        if torrents:
            lines.append(f"*⬇️ Descargas activas ({len(torrents)}):*")
            for t in torrents[:5]:
                lines.append(format_torrent_status(t))
            if len(torrents) > 5:
                lines.append(f"  _... y {len(torrents) - 5} más_")
        else:
            lines.append("*⬇️ Descargas:* Ninguna activa")
    except Exception as e:
        lines.append(f"*⬇️ qBittorrent:* ❌ `{e}`")

    # ── Radarr Queue ──────────────────────────────────────────────────────────
    try:
        rq = await radarr.get_queue()
        lines.append(f"\n*🎬 Cola Radarr:* {len(rq)} elemento(s)")
        for item in rq[:3]:
            lines.append(format_queue_item_radarr(item))
    except Exception as e:
        lines.append(f"\n*🎬 Radarr:* ❌ `{e}`")

    # ── Sonarr Queue ──────────────────────────────────────────────────────────
    try:
        sq = await sonarr.get_queue()
        lines.append(f"\n*📺 Cola Sonarr:* {len(sq)} elemento(s)")
        for item in sq[:3]:
            lines.append(format_queue_item_sonarr(item))
    except Exception as e:
        lines.append(f"\n*📺 Sonarr:* ❌ `{e}`")

    # ── Disk Space ───────────────────────────────────────────────────────────
    try:
        disk = get_disk_usage(settings.data_path)
        warn = " ⚠️" if disk["free"] < settings.disk_warn_threshold_gb * 1024**3 else ""
        lines.append(
            f"\n*💾 Disco:* {disk['used_h']} usados / {disk['total_h']} total "
            f"({disk['pct']}%){warn}"
        )
        lines.append(f"  Libres: {disk['free_h']}")
    except Exception as e:
        lines.append(f"\n*💾 Disco:* ❌ `{e}`")

    # ── Service Health ────────────────────────────────────────────────────────
    services = {
        "Radarr": radarr.health_check(),
        "Sonarr": sonarr.health_check(),
        "qBittorrent": qbit.health_check(),
        "Bazarr": bazarr.health_check(),
    }

    import asyncio
    health_results = await asyncio.gather(*services.values(), return_exceptions=True)
    health = dict(zip(services.keys(), health_results))

    lines.append("\n*🔧 Servicios:*")
    for svc, up in health.items():
        icon = "✅" if up is True else "❌"
        lines.append(f"  {icon} {svc}")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


@restricted
async def wanted_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Buscando pendientes...")
    lines = ["*📋 Pendientes de descarga*\n"]

    try:
        movies = await radarr.get_wanted()
        lines.append(f"*🎬 Películas ({len(movies)}):*")
        if movies:
            for m in movies[:8]:
                lines.append(f"  • {m.get('title', '?')} ({m.get('year', '?')})")
        else:
            lines.append("  Ninguna")
    except Exception as e:
        lines.append(f"*🎬 Radarr:* ❌ `{e}`")

    try:
        episodes = await sonarr.get_wanted()
        lines.append(f"\n*📺 Episodios ({len(episodes)}):*")
        if episodes:
            for ep in episodes[:8]:
                series = ep.get("series", {}).get("title", "?")
                sn = ep.get("seasonNumber", 0)
                en = ep.get("episodeNumber", 0)
                lines.append(f"  • {series} S{sn:02d}E{en:02d}")
        else:
            lines.append("  Ninguno")
    except Exception as e:
        lines.append(f"\n*📺 Sonarr:* ❌ `{e}`")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")
