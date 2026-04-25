from .base import BaseArrClient
from ..config import settings


class SonarrClient(BaseArrClient):
    def __init__(self):
        super().__init__(settings.sonarr_url, settings.sonarr_api_key)

    async def search_series(self, query: str) -> list:
        return await self.get("series/lookup", {"term": query})

    async def add_series(self, tvdb_id: int, title: str, monitor: str = "all",
                         quality_profile_id: int = 1, season_folder: bool = True) -> dict:
        should_search = monitor not in ("future", "none")
        payload = {
            "tvdbId": tvdb_id,
            "title": title,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": "/data/plexserver/series",
            "monitored": True,
            "seasonFolder": season_folder,
            "addOptions": {
                "monitor": monitor,
                "searchForMissingEpisodes": should_search,
            },
        }
        return await self.post("series", payload)

    async def get_all_series(self) -> list:
        return await self.get("series")

    async def update_series(self, series_id: int, payload: dict) -> dict:
        return await self.put(f"series/{series_id}", payload)

    async def set_monitor(self, series_id: int, monitored: bool) -> dict:
        series = await self.get(f"series/{series_id}")
        series["monitored"] = monitored
        return await self.put(f"series/{series_id}", series)

    async def get_queue(self) -> list:
        data = await self.get("queue", {"pageSize": 50})
        return data.get("records", [])

    async def delete_queue_item(self, item_id: int, blacklist: bool = False):
        import httpx
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
