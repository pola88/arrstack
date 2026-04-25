import httpx
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseArrClient:
    """Shared async HTTP client for all *arr services."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        }

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/api/v3/{path}",
                headers=self.headers,
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def post(self, path: str, payload: dict) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/api/v3/{path}",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def put(self, path: str, payload: dict) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.put(
                f"{self.base_url}/api/v3/{path}",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def health_check(self) -> bool:
        try:
            await self.get("system/status")
            return True
        except Exception as e:
            logger.debug(f"Health check failed for {self.base_url}: {e}")
            return False
