import importlib
import pkgutil
from app.tools.base import BaseTool

_registry: dict[str, BaseTool] = {}


def discover_tools() -> None:
    """Walk app/tools packages and register all concrete BaseTool subclasses."""
    import app.tools as tools_pkg
    for finder, module_name, is_pkg in pkgutil.walk_packages(
        path=tools_pkg.__path__,
        prefix=tools_pkg.__name__ + ".",
        onerror=lambda name: None,
    ):
        module = importlib.import_module(module_name)
        for _, obj in vars(module).items():
            if (isinstance(obj, type)
                and issubclass(obj, BaseTool)
                and obj is not BaseTool
                and not getattr(obj, "_abstract", False)):
                instance = obj()
                _registry[instance.name] = instance


def get_tool(name: str) -> BaseTool | None:
    return _registry.get(name)


def all_tools() -> list[BaseTool]:
    return list(_registry.values())
