# FAILURES.md — Known Failure Modes & System Limitations

This document lists the specific conditions under which this system can lose a DM, send a duplicate, or experience state discrepancies.

---

1. **Duplicate DM if process crashes after outbound HTTP `202` and upstream idempotency fails**
   - **Exact Condition**: The worker calls `POST /v1/dm/send` and Pseudogram responds with `202 Accepted` (`dm_id`). If the process crashes or loses power *before* `UPDATE dm_attempts SET status = 'in_flight'` commits to SQLite, the row remains `pending` on disk.
   - **Consequence**: Upon restart, the worker re-queries the pending attempt and replays the request using `Idempotency-Key: f"{user_id}:{rule_id}"`. If Pseudogram's upstream mock API fails to honor the idempotency key, a duplicate DM will be sent to the user.

2. **DM delivered despite comment deletion if `comment.deleted` arrives post-dispatch**
   - **Exact Condition**: A `comment.deleted` event arrives for a `comment_id` *after* the worker has already sent the DM request and updated the attempt status to `in_flight` or `delivered`.
   - **Consequence**: The DM will still be delivered to the recipient.
   - **Reason**: The cancellation logic executes `UPDATE dm_attempts SET status = 'cancelled' WHERE comment_id = ? AND status = 'pending'`. Once a DM is accepted by the outbound API, there is no platform mechanism to recall or un-send an Instagram DM.

3. **Suppression of DMs when the same user comments a matching keyword across multiple posts**
   - **Exact Condition**: User `usr_123` comments `"PRICE"` on Post A (triggering `rule_1`), and later comments `"PRICE"` on Post B (also matching `rule_1`).
   - **Consequence**: The second comment is blocked by SQLite's `UNIQUE (user_id, rule_id)` constraint. `INSERT ... ON CONFLICT DO NOTHING` returns 0 affected rows, and the attempt is recorded in `blocked_duplicates`. The user will receive exactly 1 DM for `rule_1` and will not get a second DM for Post B.

4. **Permanent DM loss on HTTP `400 Bad Request` or 5 consecutive retry failures**
   - **Exact Condition**: Outbound API responds with `400 Bad Request` (e.g., malformed payload or recipient DM privacy blocks), or responds with `500` continuously across all 5 exponential backoff retries.
   - **Consequence**: The attempt transitions permanently to `status = 'failed'`. Retries cease, and `/stats` records it under `failed`. The DM is intentionally abandoned to avoid infinite retry loops against invalid recipients.

5. **Temporary HTTP `429` rate-limit burst after service restart**
   - **Exact Condition**: The service restarts while the in-memory sliding window rate limiter has 10 active request timestamps recorded.
   - **Consequence**: The in-memory sliding window resets to empty upon restart. If the worker immediately attempts outbound requests, Pseudogram returns HTTP `429 Too Many Requests`. The worker handles this by extracting `Retry-After` and setting `next_attempt_at = now + Retry-After`, resulting in temporary queue processing latency without losing any DMs.
