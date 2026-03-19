from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.models import Agent, ApiKey, get_db
from app.core.auth import generate_api_key, hash_key
from app.config import get_settings

router = APIRouter()


class RegisterResponse(BaseModel):
    agent_id: str
    api_key: str
    wallet_address: str
    free_credits: float
    instruction: str


@router.post("/auth/register", response_model=RegisterResponse)
async def register(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    agent = Agent()
    db.add(agent)
    await db.flush()

    full_key, prefix = generate_api_key()
    api_key = ApiKey(
        agent_id=agent.id,
        key_hash=hash_key(full_key),
        key_prefix=prefix,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(agent)

    return RegisterResponse(
        agent_id=str(agent.id),
        api_key=full_key,
        wallet_address=agent.wallet_address,
        free_credits=float(settings.new_agent_credits),
        instruction=(
            f"Agent registered. {settings.new_agent_credits} free credits included. "
            f"Send ETH to {agent.wallet_address} and call POST /payments/crypto/deposit "
            f"with tx hash when you need more. Use api_key in X-API-Key header."
        ),
    )
