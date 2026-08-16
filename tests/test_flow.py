import hashlib
import hmac
import json
import os

# Set test DB and test API key before importing app
os.environ["DATABASE_PATH"] = "test_instagram_auto.db"
os.environ["PSEUDOGRAM_API_KEY"] = "test_secret_key"

import pytest
from fastapi.testclient import TestClient

from app.db import close_db, get_connection, init_db
from app.main import app

client = TestClient(app)
SECRET = "test_secret_key"


def sign_payload(payload_bytes: bytes) -> str:
    sig = hmac.new(SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.fixture(autouse=True)
def clean_db():
    close_db()
    if os.path.exists("test_instagram_auto.db"):
        os.remove("test_instagram_auto.db")
    init_db("test_instagram_auto.db")
    yield
    close_db()
    if os.path.exists("test_instagram_auto.db"):
        os.remove("test_instagram_auto.db")


def test_create_rule():
    response = client.post("/rules", json={"keyword": "PRICE", "dm_message": "Check your DMs for pricing!"})
    assert response.status_code == 201
    data = response.json()
    assert "rule_id" in data
    assert data["keyword"] == "PRICE"
    assert data["dm_message"] == "Check your DMs for pricing!"


def test_webhook_signature_verification():
    # 1. Missing signature header
    payload = {
        "event_id": "evt_101",
        "event_type": "comment.created",
        "data": {
            "comment_id": "cmt_1",
            "post_id": "post_1",
            "text": "PRICE please",
            "from": {"user_id": "usr_1", "username": "alice"},
        },
    }
    raw = json.dumps(payload).encode("utf-8")

    res = client.post("/webhook", content=raw)
    assert res.status_code == 401

    # 2. Invalid signature
    res = client.post("/webhook", content=raw, headers={"X-PseudoGram-Signature": "sha256=invalid"})
    assert res.status_code == 401

    # 3. Valid signature
    sig = sign_payload(raw)
    res = client.post("/webhook", content=raw, headers={"X-PseudoGram-Signature": sig})
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_webhook_deduplication_and_stats():
    # Create rule
    client.post("/rules", json={"keyword": "price", "dm_message": "Special deal link"})

    payload = {
        "event_id": "evt_201",
        "event_type": "comment.created",
        "data": {
            "comment_id": "cmt_201",
            "post_id": "post_1",
            "text": "Can I get the Price please?",
            "from": {"user_id": "usr_99", "username": "bob"},
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = sign_payload(raw)

    # Redeliver the exact same payload 5 times
    for _ in range(5):
        res = client.post("/webhook", content=raw, headers={"X-PseudoGram-Signature": sig})
        assert res.status_code == 200

    # Fetch stats
    stats_res = client.get("/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()

    assert stats["queued"] == 1
    assert stats["duplicates_blocked"] == 4
    assert stats["sent"] == 0
    assert stats["failed"] == 0


def test_comment_deleted_cancels_pending():
    client.post("/rules", json={"keyword": "discount", "dm_message": "20% off code!"})

    create_payload = {
        "event_id": "evt_301",
        "event_type": "comment.created",
        "data": {
            "comment_id": "cmt_301",
            "post_id": "post_1",
            "text": "Give me DISCOUNT",
            "from": {"user_id": "usr_301", "username": "charlie"},
        },
    }
    raw_create = json.dumps(create_payload).encode("utf-8")
    sig_create = sign_payload(raw_create)
    client.post("/webhook", content=raw_create, headers={"X-PseudoGram-Signature": sig_create})

    # Stats before deletion
    stats1 = client.get("/stats").json()
    assert stats1["queued"] == 1

    # Send comment.deleted
    delete_payload = {
        "event_id": "evt_302",
        "event_type": "comment.deleted",
        "data": {
            "comment_id": "cmt_301",
        },
    }
    raw_delete = json.dumps(delete_payload).encode("utf-8")
    sig_delete = sign_payload(raw_delete)
    client.post("/webhook", content=raw_delete, headers={"X-PseudoGram-Signature": sig_delete})

    # Stats after deletion (queued should be 0 because attempt was cancelled)
    stats2 = client.get("/stats").json()
    assert stats2["queued"] == 0
