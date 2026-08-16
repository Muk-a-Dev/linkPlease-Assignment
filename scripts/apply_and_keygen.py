import os
import sys
import httpx

PSEUDOGRAM_BASE_URL = os.getenv("PSEUDOGRAM_BASE_URL", "https://pseudogram-api.onrender.com")


def apply_and_keygen(name: str, email: str, phone: str, linkedin_url: str, whatsapp: str = None):
    """
    Step 1: POST /v1/apply
    Step 2: POST /v1/keygen
    """
    apply_payload = {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin_url,
    }
    if whatsapp:
        apply_payload["whatsapp"] = whatsapp

    print(f"1️⃣ Applying for API key on {PSEUDOGRAM_BASE_URL}/v1/apply ...")
    res1 = httpx.post(f"{PSEUDOGRAM_BASE_URL}/v1/apply", json=apply_payload, timeout=15.0)
    print(f"   Status: {res1.status_code}")
    print(f"   Response: {res1.text}")

    if res1.status_code not in (200, 201):
        print("   ⚠️ Application might already exist or failed. Proceeding to keygen...")

    print(f"\n2️⃣ Requesting API Key on {PSEUDOGRAM_BASE_URL}/v1/keygen ...")
    res2 = httpx.post(f"{PSEUDOGRAM_BASE_URL}/v1/keygen", json={"email": email}, timeout=15.0)
    print(f"   Status: {res2.status_code}")
    print(f"   Response: {res2.text}")

    if res2.status_code == 200:
        data = res2.json()
        api_key = data.get("api_key")
        print(f"\n🎉 SUCCESS! Your API Key is: {api_key}")
        print(f"Add this to your environment variables:")
        print(f"   export PSEUDOGRAM_API_KEY=\"{api_key}\"")
        return api_key
    else:
        print("\n❌ Failed to retrieve API key.")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 scripts/apply_and_keygen.py <name> <email> <phone> <linkedin_url> [whatsapp]")
        print("Example: python3 scripts/apply_and_keygen.py \"Mukul\" \"mukul@example.com\" \"+919876543210\" \"https://linkedin.com/in/mukul\"")
        sys.exit(1)

    name = sys.argv[1]
    email = sys.argv[2]
    phone = sys.argv[3]
    linkedin_url = sys.argv[4]
    whatsapp = sys.argv[5] if len(sys.argv) > 5 else None

    apply_and_keygen(name, email, phone, linkedin_url, whatsapp)
