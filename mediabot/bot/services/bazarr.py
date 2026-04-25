import httpx
import logging
from ..config import settings

logger = logging.getLogger(__name__)


class BazarrClient:
    def __init__(self):
        self.url = settings.bazarr_url.rstrip("/")
        self.headers = {"X-Api-Key": settings.bazarr_api_key}

    async def search_subtitles_movie(self, radarr_id: int) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{self.url}/api/movies",
                headers=self.headers,
                params={"radarrid": radarr_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def search_subtitles_episode(self, sonarr_episode_id: int) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{self.url}/api/episodes",
                headers=self.headers,
                params={"episodeid": sonarr_episode_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_wanted_movies(self) -> list:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.url}/api/movies/wanted",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    async def get_wanted_episodes(self) -> list:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.url}/api/episodes/wanted",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.url}/api/system/status",
                    headers=self.headers,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.debug(f"Bazarr health check failed: {e}")
            return False
