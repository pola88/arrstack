from .base import BaseArrClient
from ..config import settings


class ProwlarrClient(BaseArrClient):
    def __init__(self):
        super().__init__(settings.prowlarr_url, settings.prowlarr_api_key)

    async def search(self, query: str, categories: list = None) -> list:
        params = {"query": query}
        if categories:
            params["categories"] = ",".join(str(c) for c in categories)
        return await self.get("search", params)

    async def get_indexers(self) -> list:
        return await self.get("indexer")
