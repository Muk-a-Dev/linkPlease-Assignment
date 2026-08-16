import os
from typing import Any, Dict, Optional, Tuple
import httpx

PSEUDOGRAM_BASE_URL = os.getenv("PSEUDOGRAM_BASE_URL", "https://pseudogram-api.onrender.com")
PSEUDOGRAM_API_KEY = os.getenv("PSEUDOGRAM_API_KEY", "test_secret")


class PseudogramClient:
    def __init__(self, base_url: str = PSEUDOGRAM_BASE_URL, api_key: str = PSEUDOGRAM_API_KEY, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def send_dm(
        self,
        recipient_user_id: str,
        message: str,
        comment_id: str,
        idempotency_key: str,
    ) -> Tuple[int, Optional[Dict[str, Any]], Dict[str, str]]:
        """
        Design decision 3: Idempotency-Key is deterministic: f"{user_id}:{rule_id}".
        """
        url = f"{self.base_url}/v1/dm/send"
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "X-API-Key": self.api_key,
        }
        payload = {
            "recipient_user_id": recipient_user_id,
            "message": message,
            "comment_id": comment_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                resp_data = None
                try:
                    resp_data = response.json()
                except Exception:
                    pass
                return response.status_code, resp_data, dict(response.headers)
            except httpx.HTTPError as exc:
                return 500, {"error": str(exc)}, {}

    async def get_dm_status(self, dm_id: str) -> Tuple[int, Optional[Dict[str, Any]]]:
        url = f"{self.base_url}/v1/dm/{dm_id}"
        headers = {"X-API-Key": self.api_key}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                resp_data = None
                try:
                    resp_data = response.json()
                except Exception:
                    pass
                return response.status_code, resp_data
            except httpx.HTTPError as exc:
                return 500, {"error": str(exc)}
