from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: dict[str, Any]
    error: str | None = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    price_per_call: Decimal = Decimal("0")
    daily_free_limit: int | None = None  # None = no free tier

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    @property
    def billing_mode(self) -> str:
        if self.price_per_call == 0 and self.daily_free_limit is None:
            return "free"
        if self.price_per_call == 0:
            return "free_with_limit"
        if self.daily_free_limit is not None:
            return "hybrid"
        return "paid"

    @property
    def short_pricing(self) -> str:
        if self.billing_mode == "free":
            return "free"
        if self.billing_mode == "free_with_limit":
            return f"free {self.daily_free_limit}/day"
        if self.billing_mode == "hybrid":
            return f"free {self.daily_free_limit}/day, then {self.price_per_call}/call"
        return f"{self.price_per_call}/call"
