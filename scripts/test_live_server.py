import hashlib
import hmac
import json
import os
import sys
import httpx

API_KEY = os.getenv("PSEUDOGRAM_API_KEY", "bXVrdWwud29rQGdtYWlsLmNvbQ.927e41f09fcf452df2e3")


def test_live_server(base_url: str):
    base_url = base_url.rstrip("/")
    print(f"🚀 Testing live server at: {base_url}")

    # 1. Create a rule on the live server
    print("\n1️⃣ Creating rule via POST /rules...")
    res = httpx.post(
        f"{base_url}/rules",
        json={"keyword": "PRICE", "dm_message": "Here is the price list!"},
        timeout=15.0,
    )
    print(f"   Status: {res.status_code}, Body: {res.text}")

    # 2. Send 5 duplicate webhook events
    print("\n2️⃣ Sending 5 redelivered webhook comment events...")
    payload = {
        "event_id": "evt_live_test_01",
        "event_type": "comment.created",
        "data": {
            "comment_id": "cmt_live_01",
            "post_id": "post_live_01",
            "text": "What is the PRICE?",
            "from": {"user_id": "usr_live_mukul_99", "username": "mukul"},
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(API_KEY.encode(), raw, hashlib.sha256).hexdigest()

    for i in range(1, 6):
        r = httpx.post(
            f"{base_url}/webhook",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-PseudoGram-Signature": sig,
            },
            timeout=15.0,
        )
        print(f"   Delivery {i}/5 -> Status: {r.status_code}")

    # 3. Check stats on the live server
    print("\n3️⃣ Fetching live stats from GET /stats...")
    stats_res = httpx.get(f"{base_url}/stats", timeout=15.0)
    print(f"   Response: {stats_res.text}")
    print("\n👉 Now refresh your browser at:", f"{base_url}/stats")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://linkplease-assignment-gvcs.onrender.com"
    test_live_server(url)
