import asyncio
import time
from typing import List
from app.db import get_pending_attempts, update_attempt_status
from app.pseudogram_client import PseudogramClient


class SlidingWindowRateLimiter:
    """
    Design decision 5: Rate limiter is intentionally in-memory sliding window.
    Limits outbound calls to max_requests (10) within window_seconds (60s).
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: List[float] = []

    async def acquire(self) -> None:
        while True:
            now = time.time()
            self.timestamps = [t for t in self.timestamps if now - t < self.window_seconds]
            if len(self.timestamps) < self.max_requests:
                self.timestamps.append(now)
                return
            wait_time = self.window_seconds - (now - self.timestamps[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)


class Worker:
    def __init__(
        self,
        client: PseudogramClient,
        rate_limiter: SlidingWindowRateLimiter,
        max_attempts: int = 5,
    ):
        self.client = client
        self.rate_limiter = rate_limiter
        self.max_attempts = max_attempts
        self.running = False

    async def run(self) -> None:
        self.running = True
        while self.running:
            try:
                pending_items = await get_pending_attempts(limit=10)
                if not pending_items:
                    await asyncio.sleep(1.0)
                    continue

                for item in pending_items:
                    if not self.running:
                        break

                    await self.rate_limiter.acquire()

                    attempt_id = item["id"]
                    user_id = item["user_id"]
                    rule_id = item["rule_id"]
                    comment_id = item["comment_id"]
                    dm_message = item["dm_message"]
                    current_attempts = item["attempts"]
                    idempotency_key = f"{user_id}:{rule_id}"

                    status_code, data, headers = await self.client.send_dm(
                        recipient_user_id=user_id,
                        message=dm_message,
                        comment_id=comment_id,
                        idempotency_key=idempotency_key,
                    )

                    now = time.time()

                    if status_code == 202 and data and "dm_id" in data:
                        dm_id = data["dm_id"]
                        await update_attempt_status(
                            attempt_id=attempt_id,
                            status="in_flight",
                            dm_id=dm_id,
                            increment_attempts=True,
                        )
                    elif status_code == 429:
                        retry_after = 60.0
                        if "Retry-After" in headers:
                            try:
                                retry_after = float(headers["Retry-After"])
                            except ValueError:
                                pass
                        await update_attempt_status(
                            attempt_id=attempt_id,
                            status="pending",
                            next_attempt_at=now + retry_after,
                            last_error="429 Rate limited",
                        )
                    elif status_code == 400:
                        await update_attempt_status(
                            attempt_id=attempt_id,
                            status="failed",
                            last_error="400 Bad request",
                            increment_attempts=True,
                        )
                    else:
                        new_attempt_count = current_attempts + 1
                        if new_attempt_count >= self.max_attempts:
                            await update_attempt_status(
                                attempt_id=attempt_id,
                                status="failed",
                                last_error=f"Max attempts ({self.max_attempts}) reached with status {status_code}",
                                increment_attempts=True,
                            )
                        else:
                            backoff = min(60.0, float(2**new_attempt_count))
                            await update_attempt_status(
                                attempt_id=attempt_id,
                                status="pending",
                                next_attempt_at=now + backoff,
                                last_error=f"Transient error status {status_code}",
                                increment_attempts=True,
                            )
            except Exception:
                await asyncio.sleep(1.0)

    def stop(self) -> None:
        self.running = False
