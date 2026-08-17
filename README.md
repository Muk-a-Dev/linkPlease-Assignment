# Instagram Automation Backend Service

A resilient single-process FastAPI service built to handle unreliable upstream comment webhooks (redelivery, out-of-order events) and hostile outbound DM API behaviors (rate limiting, transient errors, deferred delivery failures).

---

## Architecture & System Design Highlights

1. **SQLite Disk-Backed Queue**: All state transitions (`pending`, `in_flight`, `delivered`, `failed`, `cancelled`) live on disk in SQLite running in **WAL mode** (`PRAGMA journal_mode=WAL;`). Survived service restarts with zero lost messages.
2. **Atomic DB Constraint Deduplication**: `dm_attempts` enforces `UNIQUE (user_id, rule_id)`. The webhook performs `INSERT ... ON CONFLICT (user_id, rule_id) DO NOTHING`. SQLite write serialization eliminates read-then-write race conditions under concurrent event redelivery.
3. **Deterministic Idempotency Key**: Outbound requests to `POST /v1/dm/send` include `Idempotency-Key: f"{user_id}:{rule_id}"`. Post-crash retries safely return original `dm_id`s without duplicate sends.
4. **Rate Limiting & Exponential Backoff**: In-memory sliding window rate limiter (10 req / 60s) and exponential backoff retries (up to 5 attempts) on transient HTTP `500` errors, respecting `Retry-After` on `429` responses.
5. **Part C Delivery Reconciler**: Background task polling `in_flight` rows older than ~30s via `GET /v1/dm/{dm_id}` to resolve terminal delivery states.
6. **Selective Comment Cancellation**: `comment.deleted` events cancel pending attempts (`WHERE status = 'pending'`).

---

## API Contract

### `POST /webhook`
- Receives comment events (`comment.created` or `comment.deleted`).
- Validates `X-PseudoGram-Signature: sha256=<hex>` HMAC-SHA256 signature using the API key secret.
- Returns `200 OK` fast (<5s).

### `POST /rules`
- Request body: `{"keyword": "PRICE", "dm_message": "Here is the price list: ..."}`
- Returns `201 Created` with `{"rule_id": "rule_...", "keyword": "PRICE", "dm_message": "..."}`. Keyword matching is case-insensitive substring matching.

### `GET /stats`
- Returns live persisted state metrics:
  ```json
  {
    "sent": 142,
    "failed": 3,
    "queued": 8,
    "duplicates_blocked": 57
  }
  ```

### `GET /health`
- Health check endpoint returning `{"status": "ok"}`.

---

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI app & background lifespan task manager
│   ├── db.py                # SQLite WAL connection, DDL, atomic ON CONFLICT dedup
│   ├── schemas.py           # Pydantic V2 models for requests & webhooks
│   ├── signature.py         # HMAC-SHA256 body signature verification
│   ├── pseudogram_client.py # HTTP client wrapper with X-API-Key and idempotency headers
│   ├── worker.py            # Async worker with rate limiter & exponential backoff
│   ├── reconciler.py        # Part C delivery reconciler
│   └── routes/
│       ├── rules.py         # POST /rules route
│       ├── webhook.py       # POST /webhook route
│       └── stats.py         # GET /stats route
├── scripts/                 # Utility scripts (demo, apply_and_keygen, simulate, submit, test_live_server, LOOM_SCRIPT)
├── tests/                   # Pytest automated test suite
├── FAILURES.md              # Detailed analysis of edge-case failure modes
├── requirements.txt         # Dependency manifest
├── Procfile                 # Deployment process entrypoint
├── Dockerfile               # Container deployment spec
└── .gitignore               # Excludes SQLite database files and bytecode
```

---

## Quickstart & Testing

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Automated Test Suite
```bash
python3 -m pytest tests/ -v
```

### 3. Run Automated Demo Script
```bash
python3 scripts/demo_test.py
```

### 4. Start Local Application
```bash
uvicorn app.main:app --reload --port 8000
```
