import asyncio
import os
import time
import pytest

os.environ["DATABASE_PATH"] = "test_worker_reconciler.db"

from app.db import (
    close_db,
    get_connection,
    get_pending_attempts,
    get_stats,
    init_db,
    insert_dm_attempt_or_dedup,
    add_rule,
)
from app.pseudogram_client import PseudogramClient
from app.reconciler import Reconciler
from app.worker import SlidingWindowRateLimiter, Worker


@pytest.fixture(autouse=True)
def clean_db():
    close_db()
    if os.path.exists("test_worker_reconciler.db"):
        os.remove("test_worker_reconciler.db")
    init_db("test_worker_reconciler.db")
    yield
    close_db()
    if os.path.exists("test_worker_reconciler.db"):
        os.remove("test_worker_reconciler.db")


class MockPseudogramClient(PseudogramClient):
    def __init__(self):
        super().__init__()
        self.send_dm_calls = []
        self.send_dm_responses = []
        self.get_dm_status_responses = {}

    async def send_dm(self, recipient_user_id, message, comment_id, idempotency_key):
        self.send_dm_calls.append(
            {
                "recipient_user_id": recipient_user_id,
                "message": message,
                "comment_id": comment_id,
                "idempotency_key": idempotency_key,
            }
        )
        if self.send_dm_responses:
            return self.send_dm_responses.pop(0)
        return 202, {"dm_id": "dm_mock_123", "status": "queued"}, {}

    async def get_dm_status(self, dm_id):
        if dm_id in self.get_dm_status_responses:
            return self.get_dm_status_responses[dm_id]
        return 200, {"dm_id": dm_id, "status": "delivered"}


def test_worker_202_accepted():
    async def _test():
        await add_rule("rule_1", "price", "Here is price link")
        await insert_dm_attempt_or_dedup("evt_1", "usr_10", "rule_1", "cmt_10", "post_10")

        mock_client = MockPseudogramClient()
        mock_client.send_dm_responses = [(202, {"dm_id": "dm_abc_1"}, {})]

        rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0)

        pending_items = await get_pending_attempts(10)
        assert len(pending_items) == 1

        await rate_limiter.acquire()
        item = pending_items[0]
        idempotency_key = f"{item['user_id']}:{item['rule_id']}"
        assert idempotency_key == "usr_10:rule_1"

    asyncio.run(_test())


def test_reconciler_delivered_transition():
    async def _test():
        await add_rule("rule_1", "price", "Message")
        await insert_dm_attempt_or_dedup("evt_1", "usr_20", "rule_1", "cmt_20", "post_20")

        conn = get_connection()
        with conn:
            conn.execute(
                "UPDATE dm_attempts SET status = 'in_flight', dm_id = 'dm_test_99', updated_at = ?",
                (time.time() - 40,),
            )

        mock_client = MockPseudogramClient()
        mock_client.get_dm_status_responses["dm_test_99"] = (
            200,
            {"dm_id": "dm_test_99", "status": "delivered"},
        )

        in_flight = conn.execute("SELECT id, dm_id FROM dm_attempts WHERE status = 'in_flight'").fetchall()
        assert len(in_flight) == 1

        status_code, data = await mock_client.get_dm_status("dm_test_99")
        assert status_code == 200
        assert data["status"] == "delivered"

        conn.execute("UPDATE dm_attempts SET status = 'delivered' WHERE id = ?", (in_flight[0]["id"],))

        stats = await get_stats()
        assert stats["sent"] == 1
        assert stats["queued"] == 0

    asyncio.run(_test())
