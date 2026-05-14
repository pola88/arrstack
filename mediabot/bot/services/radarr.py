from .base import BaseArrClient
from ..config import settings
import httpx


class RadarrClient(BaseArrClient):
    def __init__(self):
        super().__init__(settings.radarr_url, settings.radarr_api_key)

    async def _get_root_folder(self) -> str:
        folders = await self.get("rootfolder")
        if not folders:
            raise Exception("No hay carpetas raíz configuradas en Radarr")
        return folders[0]["path"]

    async def search_movie(self, query: str) -> list:
        return await self.get("movie/lookup", {"term": query})

    async def add_movie(self, tmdb_id: int, title: str, year: int,
                        quality_profile_id: int = 1) -> dict:
        root_path = await self._get_root_folder()
        payload = {
            "tmdbId": tmdb_id,
            "title": title,
            "year": year,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_path,
            "monitored": True,
            "addOptions": {"searchForMovie": True},
        }
        return await self.post("movie", payload)

    async def get_all_movies(self) -> list:
        return await self.get("movie")

    async def update_movie(self, movie_id: int, payload: dict) -> dict:
        return await self.put(f"movie/{movie_id}", payload)

    async def delete_movie(self, movie_id: int, blacklist: bool = False):
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{self.base_url}/api/v3/movie/{movie_id}",
                headers=self.headers,
                params={
                    "deleteFiles": False,
                    "addImportExclusion": blacklist,
                },
            )
            resp.raise_for_status()

    async def get_queue(self) -> list:
        data = await self.get("queue", {"pageSize": 50})
        return data.get("records", [])

    async def delete_queue_item(self, item_id: int, blacklist: bool = False):
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{self.base_url}/api/v3/queue/{item_id}",
                headers=self.headers,
                params={"removeFromClient": True, "blacklist": blacklist},
            )
            resp.raise_for_status()

    async def retry_queue_item(self, item_id: int) -> dict:
        return await self.post(f"queue/grab/{item_id}", {})

    async def get_wanted(self) -> list:
        data = await self.get("wanted/missing", {"pageSize": 15})
        return data.get("records", [])

    async def get_quality_profiles(self) -> list:
        return await self.get("qualityprofile")

    async def get_history(self, page_size: int = 10) -> list:
        data = await self.get("history", {
            "pageSize": page_size,
            "sortKey": "date",
            "sortDirection": "descending",
        })
        return data.get("records", [])

    async def health_check(self) -> bool:
        try:
            await self.get("system/status")
            return True
        except Exception:
            return False