import uuid
from fastapi import APIRouter, status
from app.db import add_rule
from app.schemas import RuleCreate, RuleResponse

router = APIRouter()


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(rule: RuleCreate):
    rule_id = f"rule_{uuid.uuid4().hex[:12]}"
    created = await add_rule(rule_id=rule_id, keyword=rule.keyword, dm_message=rule.dm_message)
    return RuleResponse(**created)
