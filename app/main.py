from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.tools.registry import discover_tools
from app.api.routes import auth, skills, balance, execute, payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    discover_tools()
    yield


app = FastAPI(
    title="Actly",
    version="2.0.0",
    description="Agent-first AI tool marketplace. Zero human in the loop.",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(skills.router)
app.include_router(balance.router)
app.include_router(execute.router)
app.include_router(payments.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/.well-known/agent-capabilities.json")
async def manifest():
    from app.config import get_settings
    from app.tools.registry import all_tools
    settings = get_settings()
    tools = all_tools()
    base = settings.base_url

    return {
        "platform": "Actly",
        "version": "4",
        "description": "Agent-first tool marketplace with crypto-native payments.",
        "register": {
            "method": "POST",
            "url": f"{base}/auth/register",
            "body": {},
        },
        "tools": {
            "list": f"{base}/skills",
            "execute": f"{base}/execute",
        },
        "credits": {
            "balance": f"{base}/balance",
            "crypto_deposit": f"{base}/payments/crypto/deposit",
            "stripe": f"{base}/payments/stripe",
        },
        "mcp": f"{base}/mcp",
        "tools_summary": [
            {
                "name": t.name,
                "description": t.description,
                "price": str(t.price_per_call),
                "daily_free_limit": t.daily_free_limit,
            }
            for t in tools
        ],
    }


@app.post("/mcp")
async def mcp(request: dict):
    """
    Minimal MCP endpoint. JSON-RPC 2.0.
    Handles: initialize, tools/list, tools/call
    """
    from app.tools.registry import all_tools, get_tool
    from app.core.auth import verify_key, extract_prefix
    from sqlalchemy import select
    from app.models import Agent, ApiKey
    from app.models import async_session
    import uuid

    method = request.get("method", "")
    params = request.get("params", {})
    rid = request.get("id")

    def ok(result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def err(code, msg):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}

    # initialize
    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "actly", "version": "2.0.0"},
            "capabilities": {"tools": {}},
        })

    # tools/list
    if method == "tools/list":
        return ok({
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in all_tools()
            ]
        })

    # tools/call
    if method == "tools/call":
        api_key = params.get("_api_key") or ""
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if not api_key:
            return err(-32001, "Missing X-API-Key")

        async with async_session() as db:
            prefix = extract_prefix(api_key)
            result = await db.execute(
                select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active == True)
            )
            candidates = result.scalars().all()
            agent = None
            for candidate in candidates:
                if verify_key(api_key, candidate.key_hash):
                    r = await db.execute(select(Agent).where(Agent.id == candidate.agent_id))
                    agent = r.scalar_one_or_none()
                    break

            if not agent:
                return err(-32001, "Invalid API key")

            tool = get_tool(tool_name)
            if not tool:
                return err(-32002, f"Tool '{tool_name}' not found")

            result = await tool.execute(tool_args)
            return ok({
                "content": [{"type": "text", "text": str(result.output)}],
                "isError": not result.success,
            })

    return err(-32601, f"Method '{method}' not found")
