import os
import sys
import time
import httpx

PSEUDOGRAM_BASE_URL = os.getenv("PSEUDOGRAM_BASE_URL", "https://pseudogram-api.onrender.com")
API_KEY = os.getenv("PSEUDOGRAM_API_KEY")


def run_simulation(webhook_url: str, count: int = 500, duration_seconds: int = 10):
    if not API_KEY:
        print("❌ Error: PSEUDOGRAM_API_KEY environment variable is not set!")
        print("Run: export PSEUDOGRAM_API_KEY=\"your_key_here\"")
        sys.exit(1)

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    payload = {
        "webhook_url": webhook_url,
        "count": count,
        "duration_seconds": duration_seconds,
    }

    print(f"🚀 Starting simulation run on {PSEUDOGRAM_BASE_URL}/v1/simulate/start...")
    print(f"   Webhook URL:      {webhook_url}")
    print(f"   Event count:      {count}")
    print(f"   Duration seconds: {duration_seconds}")

    res = httpx.post(f"{PSEUDOGRAM_BASE_URL}/v1/simulate/start", json=payload, headers=headers, timeout=20.0)
    print(f"   Status Code: {res.status_code}")
    print(f"   Response:    {res.text}")

    if res.status_code != 200:
        print("❌ Simulation failed to start.")
        return

    data = res.json()
    run_id = data.get("run_id")
    print(f"\n⏳ Simulation started! Run ID: {run_id}")
    print(f"Waiting {duration_seconds + 5} seconds for simulation events to deliver and reconcile...")
    time.sleep(duration_seconds + 5)

    print(f"\n📊 Fetching truth data from {PSEUDOGRAM_BASE_URL}/v1/simulate/{run_id}/truth...")
    res_truth = httpx.get(f"{PSEUDOGRAM_BASE_URL}/v1/simulate/{run_id}/truth", headers=headers, timeout=20.0)
    print(f"   Status Code: {res_truth.status_code}")
    print(f"   Truth Data:  {res_truth.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/simulate_test.py <webhook_url> [count] [duration_seconds]")
        print("Example: python3 scripts/simulate_test.py \"https://your-app.example.com/webhook\" 500 10")
        sys.exit(1)

    url = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    run_simulation(url, count, duration)
