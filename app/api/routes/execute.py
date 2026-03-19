import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, ApiKey, ExecutionLog, get_db
from app.core.auth import verify_key, extract_prefix
from app.tools.registry import get_tool
from app.core.credits import deduct_credits
from app.config import get_settings

router = APIRouter()
settings = get_settings()


async def get_agent(db: AsyncSession, key: str) -> Agent | None:
    prefix = extract_prefix(key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active == True)
    )
    candidates = result.scalars().all()
    for candidate in candidates:
        if verify_key(key, candidate.key_hash):
            agent_result = await db.execute(select(Agent).where(Agent.id == candidate.agent_id))
            return agent_result.scalar_one_or_none()
    return None


class ExecuteRequest(BaseModel):
    tool: str
    params: dict = {}


async def _check_free_quota(db: AsyncSession, agent_id: uuid.UUID, tool_name: str, daily_limit: int) -> bool:
    """Return True if agent still has free quota for this tool today."""
    if daily_limit is None:
        return False
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(ExecutionLog.id)).where(
            ExecutionLog.agent_id == agent_id,
            ExecutionLog.tool == tool_name,
            ExecutionLog.was_free == True,
            ExecutionLog.status == "success",
            ExecutionLog.created_at >= cutoff,
        )
    )
    used = result.scalar_one()
    return used < daily_limit


@router.post("/execute")
async def execute(
    req: ExecuteRequest,
    x_api_key: str = Header(),
    db: AsyncSession = Depends(get_db),
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    agent = await get_agent(db, x_api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    tool = get_tool(req.tool)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool}' not found")

    # Check free quota
    is_free = await _check_free_quota(db, agent.id, tool.name, tool.daily_free_limit)
    is_paid = tool.price_per_call > 0

    # If not free and not paid (fully free tool with no limit), proceed
    # If paid and no free quota left, check credits
    if is_paid and not is_free:
        if agent.credits < tool.price_per_call:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "insufficient_credits",
                    "required": str(tool.price_per_call),
                    "available": str(agent.credits),
                    "wallet_address": agent.wallet_address,
                    "deposit_endpoint": f"{settings.base_url}/payments/crypto/deposit",
                    "stripe_topup": f"{settings.base_url}/payments/stripe",
                },
            )

    # Execute
    start = time.monotonic()
    result = await tool.execute(req.params)
    duration_ms = int((time.monotonic() - start) * 1000)

    credits_charged = Decimal("0")
    if result.success and is_paid and not is_free:
        ok = await deduct_credits(
            db, agent.id, tool.price_per_call,
            idempotency_key=f"exec_{uuid.uuid4()}"
        )
        credits_charged = tool.price_per_call if ok else Decimal("0")

    log = ExecutionLog(
        agent_id=agent.id,
        tool=tool.name,
        params=json.dumps(req.params),
        output=json.dumps(result.output),
        credits_charged=credits_charged,
        was_free=(result.success and (is_free or tool.price_per_call == 0)),
        status="success" if result.success else "error",
        duration_ms=duration_ms,
    )
    db.add(log)
    await db.commit()

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Tool execution failed")

    return {
        "execution_id": str(log.id),
        "tool": tool.name,
        "output": result.output,
        "credits_charged": str(credits_charged),
        "credits_remaining": str(agent.credits),
    }
