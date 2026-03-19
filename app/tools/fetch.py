from decimal import Decimal
import httpx
from app.tools.base import BaseTool, ToolResult


class FetchTool(BaseTool):
    name = "fetch_text"
    description = (
        "Fetch the plain text of a URL via HTTP GET. "
        "No JavaScript rendering. Returns up to max_chars characters."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "default": 5000, "description": "Max characters to return"},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "url": {"type": "string"},
            "status_code": {"type": "integer"},
            "truncated": {"type": "boolean"},
        },
    }
    price_per_call = Decimal("0")
    daily_free_limit = 100

    async def execute(self, params: dict) -> ToolResult:
        url = params["url"]
        max_chars = params.get("max_chars", 5000)
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Actly/2.0"})
                text = resp.text[:max_chars]
                return ToolResult(
                    success=True,
                    output={
                        "text": text,
                        "url": str(resp.url),
                        "status_code": resp.status_code,
                        "truncated": len(resp.text) > max_chars,
                    },
                )
        except Exception as e:
            return ToolResult(success=False, output={}, error=str(e))
