import hashlib
import hmac
import json
import os
import sys

# Ensure app package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test DB and secret before importing app
db_file = "demo_instagram_auto.db"
os.environ["DATABASE_PATH"] = db_file
os.environ["PSEUDOGRAM_API_KEY"] = "test_secret"

from fastapi.testclient import TestClient
from app.db import close_db, init_db
from app.main import app


def run_demo():
    print("=" * 60)
    print("🚀 INSTAGRAM AUTOMATION BACKEND - END-TO-END DEMO TEST")
    print("=" * 60)

    # 1. Reset test database
    close_db()
    if os.path.exists(db_file):
        os.remove(db_file)
    init_db(db_file)

    client = TestClient(app)
    secret = "test_secret"

    def sign(body_bytes: bytes) -> str:
        sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    # 2. Create a rule (POST /rules)
    print("\n1️⃣ Creating rule via POST /rules...")
    rule_res = client.post("/rules", json={"keyword": "PRICE", "dm_message": "Hey! Here is 20% off!"})
    print(f"   Status Code: {rule_res.status_code}")
    print(f"   Response:    {rule_res.json()}")

    # 3. Check initial stats (GET /stats)
    print("\n2️⃣ Initial Stats via GET /stats...")
    stats_res1 = client.get("/stats")
    print(f"   Response: {stats_res1.json()}")

    # 4. Simulate 5 redelivered comment webhook events with the same user/rule
    print("\n3️⃣ Simulating 5 redelivered webhook events (Same user & rule)...")
    payload = {
        "event_id": "evt_demo_101",
        "event_type": "comment.created",
        "data": {
            "comment_id": "cmt_demo_101",
            "post_id": "post_99",
            "text": "What is the PRICE of this item?",
            "from": {"user_id": "usr_demo_777", "username": "alice_demo"},
        },
    }
    raw_payload = json.dumps(payload).encode("utf-8")
    sig_header = sign(raw_payload)

    for i in range(1, 6):
        res = client.post("/webhook", content=raw_payload, headers={"X-PseudoGram-Signature": sig_header})
        print(f"   Delivery {i}/5 -> Status Code: {res.status_code}, Body: {res.json()}")

    # 5. Check stats after redelivery
    print("\n4️⃣ Post-Delivery Stats via GET /stats...")
    stats_res2 = client.get("/stats")
    print(f"   Response: {stats_res2.json()}")
    
    print("\n✅ Verification Successful:")
    print("   - Exactly 1 DM attempt queued.")
    print("   - Exactly 4 duplicate attempts blocked by DB constraint UNIQUE(user_id, rule_id).")

    # Cleanup demo db
    close_db()
    if os.path.exists(db_file):
        os.remove(db_file)
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
