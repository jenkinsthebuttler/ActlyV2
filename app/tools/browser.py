from decimal import Decimal
import base64
from app.tools.base import BaseTool, ToolResult


class BrowserTool(BaseTool):
    name = "browser_screenshot"
    description = (
        "Take a screenshot of a web page using a headless browser. "
        "Returns a base64-encoded PNG image."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to screenshot"},
            "full_page": {"type": "boolean", "default": False, "description": "Capture entire scrollable page"},
            "viewport_width": {"type": "integer", "default": 1280},
            "viewport_height": {"type": "integer", "default": 720},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "screenshot_base64": {"type": "string"},
            "url": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
    }
    price_per_call = Decimal("0.0100")
    daily_free_limit = 2

    async def execute(self, params: dict) -> ToolResult:
        url = params["url"]
        full_page = params.get("full_page", False)
        width = params.get("viewport_width", 1280)
        height = params.get("viewport_height", 720)
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": width, "height": height})
                await page.goto(url, wait_until="networkidle")
                screenshot_bytes = await page.screenshot(full_page=full_page)
                await browser.close()
            return ToolResult(
                success=True,
                output={
                    "screenshot_base64": base64.b64encode(screenshot_bytes).decode(),
                    "url": url,
                    "width": width,
                    "height": height,
                },
            )
        except Exception as e:
            return ToolResult(success=False, output={}, error=str(e))
