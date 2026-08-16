import asyncio
import time
from app.db import get_in_flight_attempts, update_attempt_status
from app.pseudogram_client import PseudogramClient


class Reconciler:
    def __init__(
        self,
        client: PseudogramClient,
        poll_interval: float = 10.0,
        age_threshold: float = 30.0,
        max_attempts: int = 5,
    ):
        self.client = client
        self.poll_interval = poll_interval
        self.age_threshold = age_threshold
        self.max_attempts = max_attempts
        self.running = False

    async def run(self) -> None:
        self.running = True
        while self.running:
            try:
                in_flight_items = await get_in_flight_attempts(
                    older_than_seconds=self.age_threshold
                )
                for item in in_flight_items:
                    if not self.running:
                        break

                    attempt_id = item["id"]
                    dm_id = item["dm_id"]
                    attempts = item["attempts"]

                    status_code, data = await self.client.get_dm_status(dm_id)
                    now = time.time()

                    if status_code == 200 and data and "status" in data:
                        dm_status = data["status"]
                        if dm_status == "delivered":
                            await update_attempt_status(
                                attempt_id=attempt_id,
                                status="delivered",
                                dm_id=dm_id,
                            )
                        elif dm_status == "failed":
                            if attempts >= self.max_attempts:
                                await update_attempt_status(
                                    attempt_id=attempt_id,
                                    status="failed",
                                    last_error="Reconciler found DM failed after max attempts",
                                )
                            else:
                                await update_attempt_status(
                                    attempt_id=attempt_id,
                                    status="pending",
                                    next_attempt_at=now,
                                    last_error="Reconciler found DM failed, retrying",
                                )
                        elif dm_status == "queued":
                            await update_attempt_status(
                                attempt_id=attempt_id,
                                status="in_flight",
                                next_attempt_at=now,
                            )
            except Exception:
                pass

            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self.running = False
