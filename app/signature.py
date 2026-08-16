import hashlib
import hmac
import os
from fastapi import HTTPException, Request

async def verify_signature(request: Request) -> bytes:
    api_key = os.getenv("PSEUDOGRAM_API_KEY", "test_secret")
    raw_body = await request.body()
    sig_header = request.headers.get("X-PseudoGram-Signature")
    if not sig_header:
        raise HTTPException(status_code=401, detail="Missing X-PseudoGram-Signature header")

    if not sig_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid signature format")

    provided_hex = sig_header[len("sha256=") :]
    expected_hex = hmac.new(
        api_key.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hex, provided_hex):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    return raw_body
