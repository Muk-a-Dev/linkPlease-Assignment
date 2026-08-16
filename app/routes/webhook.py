import json
from fastapi import APIRouter, Depends, HTTPException
from app.db import cancel_pending_attempt, get_matching_rules, insert_dm_attempt_or_dedup
from app.schemas import WebhookPayload
from app.signature import verify_signature

router = APIRouter()


@router.post("/webhook")
async def handle_webhook(raw_body: bytes = Depends(verify_signature)):
    try:
        payload_dict = json.loads(raw_body.decode("utf-8"))
        payload = WebhookPayload.model_validate(payload_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {str(e)}")

    if payload.event_type == "comment.created":
        comment_data = payload.data
        if not comment_data.text or not comment_data.from_user:
            return {"status": "ok"}

        user_id = comment_data.from_user.user_id
        comment_id = comment_data.comment_id
        post_id = comment_data.post_id or ""

        matching_rules = await get_matching_rules(comment_data.text)
        for rule in matching_rules:
            await insert_dm_attempt_or_dedup(
                event_id=payload.event_id,
                user_id=user_id,
                rule_id=rule["rule_id"],
                comment_id=comment_id,
                post_id=post_id,
            )

    elif payload.event_type == "comment.deleted":
        comment_id = payload.data.comment_id
        await cancel_pending_attempt(comment_id)

    return {"status": "ok"}
