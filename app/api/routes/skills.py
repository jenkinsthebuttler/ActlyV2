from fastapi import APIRouter
from app.tools.registry import all_tools

router = APIRouter()


@router.get("/skills")
async def list_skills():
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "price_per_call": str(t.price_per_call),
                "billing_mode": t.billing_mode,
                "short_pricing": t.short_pricing,
                "daily_free_limit": t.daily_free_limit,
            }
            for t in all_tools()
        ]
    }


@router.get("/skills/{name}")
async def get_skill(name: str):
    from app.tools.registry import get_tool
    tool = get_tool(name)
    if not tool:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "output_schema": tool.output_schema,
        "price_per_call": str(tool.price_per_call),
        "billing_mode": tool.billing_mode,
        "short_pricing": tool.short_pricing,
        "daily_free_limit": tool.daily_free_limit,
    }
