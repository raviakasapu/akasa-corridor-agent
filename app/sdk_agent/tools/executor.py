"""Tool executor — bridges framework SingleAgent to the tool registry.

Provides create_tool_executor() factory that returns a closure compatible
with the agent_framework's tool_executor interface: (name, input_data) -> dict.

Adds logging, error handling, and timing around tool execution.
Adapted from power-bi-backend-agent-v2 pattern.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict

from .registry import execute_tool as _raw_execute

logger = logging.getLogger(__name__)


def create_tool_executor(job_id: str = None) -> Callable[[str, Dict[str, Any]], Dict[str, Any]]:
    """Create a tool executor closure for the agent framework.

    Args:
        job_id: Optional job ID for logging context. If provided, all tool
                calls will be tagged with this ID in log output.

    Returns:
        Callable matching the framework's tool_executor signature:
        (name: str, input_data: Dict[str, Any]) -> Dict[str, Any]
    """
    def executor(name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        tag = f"[{job_id}] " if job_id else ""
        start = time.monotonic()

        logger.info(f"{tag}[TOOL] {name} called with {list(input_data.keys())}")

        result = _raw_execute(name, input_data)

        elapsed = time.monotonic() - start
        success = "error" not in result if isinstance(result, dict) else True

        if success:
            summary = ""
            if isinstance(result, dict):
                summary = result.get("summary", "")
                if not summary:
                    # Auto-extract key identifiers for logging
                    for key in ("corridor_id", "flight_id", "certificate_id", "status", "score"):
                        if key in result:
                            summary += f"{key}={result[key]} "
            logger.info(f"{tag}[TOOL] {name} OK ({elapsed:.2f}s) {summary}")
        else:
            error_msg = result.get("error", "unknown") if isinstance(result, dict) else str(result)
            logger.warning(f"{tag}[TOOL] {name} FAILED ({elapsed:.2f}s): {error_msg}")

        return result

    return executor
