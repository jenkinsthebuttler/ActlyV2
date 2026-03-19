import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Transaction


async def add_credits(
    db: AsyncSession,
    agent_id: uuid.UUID,
    amount: Decimal,
    idempotency_key: str,
    tx_type: str = "topup_crypto",
) -> bool:
    """
    Add credits to agent balance. Returns True if added, False if already processed.
    Idempotent via idempotency_key on the Transaction.
    """
    try:
        result = await db.execute(
            select(Agent).where(Agent.id == agent_id).with_for_update()
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return False
        agent.credits += amount
        db.add(Transaction(
            agent_id=agent_id,
            amount=amount,
            type=tx_type,
            idempotency_key=idempotency_key,
        ))
        await db.flush()
        return True
    except IntegrityError:
        await db.rollback()
        return False


async def deduct_credits(
    db: AsyncSession,
    agent_id: uuid.UUID,
    amount: Decimal,
    idempotency_key: str,
) -> bool:
    """
    Deduct credits from agent balance. Returns True if deducted, False if insufficient.
    """
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id).with_for_update()
    )
    agent = result.scalar_one_or_none()
    if not agent or agent.credits < amount:
        return False
    agent.credits -= amount
    db.add(Transaction(
        agent_id=agent_id,
        amount=-amount,
        type="execution",
        idempotency_key=idempotency_key,
    ))
    await db.flush()
    return True
