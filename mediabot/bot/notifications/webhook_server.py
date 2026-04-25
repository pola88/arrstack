import json
import logging
from aiohttp import web
from .dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


class WebhookServer:
    """
    Lightweight aiohttp server that receives push events from:
      - Sonarr  → POST /webhook/sonarr
      - Radarr  → POST /webhook/radarr
      - Plex    → POST /webhook/plex  (multipart/form-data)

    Configure in each service:
      Sonarr/Radarr: Settings → Connect → Webhook → http://mediabot:8222/webhook/sonarr
      Plex:          Settings → Webhooks → http://mediabot:8222/webhook/plex
    """

    def __init__(self, dispatcher: NotificationDispatcher, host: str, port: int):
        self.dispatcher = dispatcher
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/health", self.health)
        self.app.router.add_post("/webhook/sonarr", self.sonarr_webhook)
        self.app.router.add_post("/webhook/radarr", self.radarr_webhook)
        self.app.router.add_post("/webhook/plex", self.plex_webhook)

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def sonarr_webhook(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            event = data.get("eventType", "unknown")
            logger.info(f"Sonarr webhook received: {event}")
            await self.dispatcher.handle_sonarr_event(event, data)
        except Exception as e:
            logger.error(f"Error processing Sonarr webhook: {e}")
        return web.Response(text="ok")

    async def radarr_webhook(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            event = data.get("eventType", "unknown")
            logger.info(f"Radarr webhook received: {event}")
            await self.dispatcher.handle_radarr_event(event, data)
        except Exception as e:
            logger.error(f"Error processing Radarr webhook: {e}")
        return web.Response(text="ok")

    async def plex_webhook(self, request: web.Request) -> web.Response:
        try:
            reader = await request.multipart()
            async for field in reader:
                if field.name == "payload":
                    raw = await field.read()
                    data = json.loads(raw)
                    await self.dispatcher.handle_plex_event(data)
                    break
        except Exception as e:
            logger.error(f"Error processing Plex webhook: {e}")
        return web.Response(text="ok")

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"Webhook server running on {self.host}:{self.port}")
