import os
import sys
import httpx

PSEUDOGRAM_BASE_URL = os.getenv("PSEUDOGRAM_BASE_URL", "https://pseudogram-api.onrender.com")


def submit_assignment(email: str, github_repo: str, working_url: str, loom_url: str, start_date: str = "2026-08-16"):
    payload = {
        "email": email,
        "github_repo": github_repo,
        "working_url": working_url,
        "loom_url": loom_url,
        "parts_completed": "A+B+C",
        "start_date": start_date,
    }

    print(f"📦 Submitting assignment to {PSEUDOGRAM_BASE_URL}/v1/submit ...")
    res = httpx.post(f"{PSEUDOGRAM_BASE_URL}/v1/submit", json=payload, timeout=20.0)
    print(f"   Status Code: {res.status_code}")
    print(f"   Response:    {res.text}")

    if res.status_code == 200:
        print("\n🎉 Submission successful!")
    else:
        print("\n❌ Submission returned error.")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 scripts/submit.py <email> <github_repo> <working_url> <loom_url> [start_date]")
        print("Example: python3 scripts/submit.py \"you@example.com\" \"https://github.com/you/repo\" \"https://app.render.com\" \"https://loom.com/share/...\"")
        sys.exit(1)

    email = sys.argv[1]
    github_repo = sys.argv[2]
    working_url = sys.argv[3]
    loom_url = sys.argv[4]
    start_date = sys.argv[5] if len(sys.argv) > 5 else "2026-08-16"

    submit_assignment(email, github_repo, working_url, loom_url, start_date)
