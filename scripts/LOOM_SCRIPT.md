# 3-Minute Loom Video Script

Use this exact script when recording your 3-minute Loom video. It answers both required questions clearly and concisely.

---

### ⏱️ Video Outline & Timing Breakdown

- **0:00 - 0:30**: Introduction & Architecture Quick Tour
- **0:30 - 1:45**: Question 1 — One Tradeoff Made & What Was Given Up
- **1:45 - 2:45**: Question 2 — What I'd Do Differently With One More Week
- **2:45 - 3:00**: Conclusion & Wrap-up

---

### 🎙️ Word-for-Word Talking Points

#### Part 1: Intro (0:00 - 0:30)
> *"Hi, I'm [Your Name]. This is my submission for the LinkPlease backend engineering assignment. I built a resilient FastAPI application backed by SQLite to handle unreliable comment webhooks and hostile outbound DM API behaviors. Here is how it works under the hood and the key decisions I made."*

---

#### Part 2: Question 1 — Tradeoff & What Was Given Up (0:30 - 1:45)
> *"The biggest tradeoff I made was choosing **SQLite with a database constraint as the primary queue**, rather than an in-memory queue like Celery, Redis, or asyncio.Queue.*
>
> *Here is why I made it: I prioritised **durable idempotency and crash recovery**. Upstream comment events are redelivered roughly 8% of the time, often concurrently. By defining a `UNIQUE (user_id, rule_id)` constraint in SQLite, `INSERT ... ON CONFLICT DO NOTHING` executes atomically. Because SQLite serializes database writes, there is zero read-then-write race window. If two duplicate events arrive at the exact same millisecond, exactly one commits and the other becomes a no-op.*
>
> *What did I give up by making this tradeoff?
> 1. **Cross-post DM flexibility**: A user who comments 'PRICE' on Post A gets a DM, but if they comment 'PRICE' on Post B later, the `(user_id, rule_id)` constraint blocks the second DM. I gave up per-post rule execution in exchange for 100% reliable deduplication across event redeliveries.
> 2. **Ultra-high throughput concurrency**: A single-file SQLite database with write locking caps throughput compared to Redis/RabbitMQ. But for single-process durability surviving restarts without losing state, SQLite was the safest choice."*

---

#### Part 3: Question 2 — What I'd Do Differently With One More Week (1:45 - 2:45)
> *"If I had one more week to prepare this for full production, here are the three things I would implement:*
>
> 1. **Move to PostgreSQL with `SELECT ... FOR UPDATE SKIP LOCKED`**: SQLite WAL is great for a single process, but horizontal scaling requires a distributed queue pattern using PostgreSQL or Redis distributed locks.
> 2. **Per-Post Rule Scoping & Event Sourcing**: I would refine the constraint to `UNIQUE (user_id, rule_id, post_id)` combined with a dedicated `processed_events (event_id PRIMARY KEY)` table. This allows users to receive DMs across different posts while still protecting against duplicate `event_id` redeliveries.
> 3. **Dead-Letter Queue (DLQ) & Observability**: Add OpenTelemetry tracing and a Dead-Letter Queue for unrecoverable errors (like HTTP 400 bad requests or privacy-blocked DMs) so creators can be notified when a DM fails permanently."*

---

#### Part 4: Conclusion (2:45 - 3:00)
> *"Thank you for reviewing my assignment! All tests are passing, FAILURES.md is documented in the root directory, and the live API is deployed. I look forward to speaking on the follow-up call!"*
