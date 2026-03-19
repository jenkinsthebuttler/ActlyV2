import stripe
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import Agent, Transaction, get_db, async_session
from app.core.auth import verify_key, extract_prefix
from app.core.credits import add_credits
from app.config import get_settings

router = APIRouter()
settings = get_settings()
ETHEREUM_RPC = "https://cloudflare-eth.com"


# ── Stripe topup ──────────────────────────────────────────────────────────────

class StripeTopupRequest(BaseModel):
    amount_usd: float = 10.0


@router.post("/payments/stripe")
async def stripe_topup(
    req: StripeTopupRequest,
    x_api_key: str = Header(),
    db = Depends(get_db),
):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    async def _get_agent(db, key):
        prefix = extract_prefix(key)
        result = await db.execute(select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active == True))
        for candidate in result.scalars().all():
            if verify_key(key, candidate.key_hash):
                r = await db.execute(select(Agent).where(Agent.id == candidate.agent_id))
                return r.scalar_one_or_none()
        return None

    from app.models import ApiKey
    agent = await _get_agent(db, x_api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Actly Credits"},
                "unit_amount": int(req.amount_usd * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{settings.base_url}/payments/success",
        cancel_url=f"{settings.base_url}/payments/cancel",
        metadata={"agent_id": str(agent.id)},
    )
    return {"payment_url": session.url, "instruction": "Open the URL to complete payment."}


@router.post("/payments/webhook")
async def stripe_webhook(request: Request, sig: str = Header(alias="Stripe-Signature")):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook not configured")
    body = await request.body()
    try:
        event = stripe.Webhook.construct_event(body, sig, settings.stripe_webhook_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] != "checkout.session.completed":
        return {"status": "ignored"}

    session = event["data"]["object"]
    agent_id_str = session.get("metadata", {}).get("agent_id")
    if not agent_id_str:
        raise HTTPException(status_code=400, detail="Missing agent_id in metadata")

    import uuid
    agent_id = uuid.UUID(agent_id_str)
    amount = Decimal(str(session["amount_total"])) / Decimal("100")

    async with async_session() as db:
        ok = await add_credits(db, agent_id, amount, idempotency_key=f"stripe_{event['id']}")
        await db.commit() if ok else db.rollback()

    return {"status": "ok", "credits_added": str(amount)}


# ── Crypto deposit ────────────────────────────────────────────────────────────

async def _verify_evm_tx(tx_hash: str, expected_address: str) -> tuple[bool, Decimal]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Check receipt (confirms block number = finalized)
            receipt_resp = await client.post(
                ETHEREUM_RPC,
                json={"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [tx_hash], "id": 1},
            )
            receipt = receipt_resp.json()
            if not receipt.get("result") or not receipt["result"].get("blockNumber"):
                return False, Decimal("0")

            # Get tx value
            tx_resp = await client.post(
                ETHEREUM_RPC,
                json={"jsonrpc": "2.0", "method": "eth_getTransactionByHash", "params": [tx_hash], "id": 2},
            )
            tx_info = tx_resp.json().get("result", {})
            to_address = (tx_info.get("to") or "").lower()
            if to_address != expected_address.lower():
                return False, Decimal("0")

            value_wei = int(tx_info.get("value", "0x0"), 16)
            value_eth = Decimal(str(value_wei)) / Decimal("1e18")
            return True, value_eth
    except Exception:
        return False, Decimal("0")


class CryptoDepositRequest(BaseModel):
    tx_hash: str


@router.post("/payments/crypto/deposit")
async def crypto_deposit(
    req: CryptoDepositRequest,
    x_api_key: str = Header(),
    db = Depends(get_db),
):
    from app.models import ApiKey

    async def _get_agent(db, key):
        prefix = extract_prefix(key)
        result = await db.execute(select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active == True))
        for candidate in result.scalars().all():
            if verify_key(key, candidate.key_hash):
                r = await db.execute(select(Agent).where(Agent.id == candidate.agent_id))
                return r.scalar_one_or_none()
        return None

    agent = await _get_agent(db, x_api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    idempotency_key = f"crypto_{req.tx_hash}"
    async with async_session() as db:
        existing = await db.execute(select(Transaction).where(Transaction.idempotency_key == idempotency_key))
        if existing.scalar_one_or_none():
            return {"status": "already_processed", "message": "This transaction was already credited."}

    valid, amount_eth = await _verify_evm_tx(req.tx_hash, agent.wallet_address)
    if not valid:
        return {
            "status": "invalid",
            "message": f"Tx not found, unconfirmed, or not sent to your wallet {agent.wallet_address}",
        }

    credits = (amount_eth * Decimal(str(settings.eth_usd_price))).quantize(Decimal("0.0001"))
    if credits <= 0:
        return {"status": "invalid", "message": "Amount too small to credit."}

    async with async_session() as db:
        ok = await add_credits(db, agent.id, credits, idempotency_key=idempotency_key)
        await db.commit() if ok else db.rollback()

    return {
        "status": "confirmed",
        "credits_added": float(credits),
        "message": f"{amount_eth:.6f} ETH → {credits} credits added.",
    }
