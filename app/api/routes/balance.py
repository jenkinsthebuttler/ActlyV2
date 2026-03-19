from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, ApiKey, ExecutionLog, get_db
from app.core.auth import verify_key, extract_prefix
from app.tools.registry import get_tool
from app.core.credits import deduct_credits

router = APIRouter()


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


class BalanceResponse(BaseModel):
    agent_id: str
    credits: float


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(x_api_key: str = Header(), db: AsyncSession = Depends(get_db)):
    agent = await get_agent(db, x_api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return BalanceResponse(agent_id=str(agent.id), credits=float(agent.credits))
