"""Tool registry — registration, discovery, and execution for drone corridor tools.

Mirrors the power-bi-backend-agent-v2 tool registry pattern.
All tools are registered via the @tool decorator and executed via execute_tool().
"""

from __future__ import annotations

import json
import logging
import traceback
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global tool registry
_tools_registry: Dict[str, Dict[str, Any]] = {}


def tool(name: str, description: str, parameters: Dict[str, Any]):
    """Decorator to register a tool function.

    Usage:
        @tool(
            name="check_block_membership",
            description="Check if drone is in assigned block",
            parameters={
                "type": "object",
                "properties": {
                    "flight_id": {"type": "string", "description": "Flight ID"},
                },
                "required": ["flight_id"],
            }
        )
        def check_block_membership(flight_id: str) -> Dict[str, Any]:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(**kwargs):
            return func(**kwargs)

        _tools_registry[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": wrapper,
        }
        logger.debug(f"Registered tool: {name}")
        return wrapper
    return decorator


def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered tool by name.

    Args:
        name: Tool name
        args: Tool arguments

    Returns:
        Tool result dict (success) or {"error": "..."} (failure)
    """
    if name not in _tools_registry:
        return {"error": f"Tool not found: {name}"}

    tool_info = _tools_registry[name]
    try:
        result = tool_info["function"](**args)
        if isinstance(result, dict):
            return result
        return {"result": result, "summary": str(result)[:200]}
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}\n{traceback.format_exc()}")
        return {"error": f"Tool execution failed: {str(e)}"}


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get all tool definitions in Claude/Bedrock API format."""
    return [
        {
            "name": info["name"],
            "description": info["description"],
            "input_schema": info["parameters"],
        }
        for info in _tools_registry.values()
    ]


def list_tool_names() -> List[str]:
    """List all registered tool names."""
    return list(_tools_registry.keys())


def get_tool_count() -> int:
    """Get number of registered tools."""
    return len(_tools_registry)
