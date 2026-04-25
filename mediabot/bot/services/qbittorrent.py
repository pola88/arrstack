import httpx
import logging
from ..config import settings

logger = logging.getLogger(__name__)


class QBittorrentClient:
    def __init__(self):
        self.url = settings.qbit_url.rstrip("/")

    async def _login(self) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.url}/api/v2/auth/login",
                data={"username": settings.qbit_user, "password": settings.qbit_pass},
                timeout=10,
            )
            return resp.cookies.get("SID", "")

    async def get_torrents(self, filter: str = "all") -> list:
        sid = await self._login()
        async with httpx.AsyncClient(cookies={"SID": sid}, timeout=10) as client:
            resp = await client.get(
                f"{self.url}/api/v2/torrents/info",
                params={"filter": filter},
            )
            return resp.json()

    async def get_transfer_info(self) -> dict:
        sid = await self._login()
        async with httpx.AsyncClient(cookies={"SID": sid}, timeout=10) as client:
            resp = await client.get(f"{self.url}/api/v2/transfer/info")
            return resp.json()

    async def health_check(self) -> bool:
        try:
            await self._login()
            return True
        except Exception as e:
            logger.debug(f"qBittorrent health check failed: {e}")
            return False
