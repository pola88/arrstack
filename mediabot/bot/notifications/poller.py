import asyncio
import logging
from ..services.radarr import RadarrClient
from ..services.sonarr import SonarrClient
from ..services.qbittorrent import QBittorrentClient
from ..utils.disk import get_disk_usage
from ..config import settings
from .dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)

# Track previous states for change detection
_service_states: dict = {}


async def poll_loop(dispatcher: NotificationDispatcher, interval: int = 300):
    """
    Background polling loop.
    Runs every `interval` seconds (default: 5 min).
    Handles:
      - Disk space warnings
      - Service up/down alerts
    """
    radarr = RadarrClient()
    sonarr = SonarrClient()
    qbit = QBittorrentClient()

    services = {
        "Radarr": radarr,
        "Sonarr": sonarr,
        "qBittorrent": qbit,
    }

    logger.info(f"Poller started (interval={interval}s)")

    while True:
        await asyncio.sleep(interval)

        # ── Disk space ───────────────────────────────────────────────────────
        try:
            disk = get_disk_usage(settings.data_path)
            free_gb = disk["free"] / 1024**3
            if free_gb < settings.disk_warn_threshold_gb:
                await dispatcher.send_disk_warning(disk["free_h"], disk["pct"])
        except Exception as e:
            logger.error(f"Disk check failed: {e}")

        # ── Service health ───────────────────────────────────────────────────
        for name, client in services.items():
            try:
                is_up = await client.health_check()
                was_up = _service_states.get(name, True)  # Assume up on first run

                if was_up and not is_up:
                    await dispatcher.send_service_down(name)
                elif not was_up and is_up:
                    await dispatcher.send_service_up(name)

                _service_states[name] = is_up
            except Exception as e:
                logger.error(f"Health check error for {name}: {e}")
