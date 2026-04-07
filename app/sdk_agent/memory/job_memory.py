"""Job memory — tracks mission state across orchestrator tasks.

Stores task results, tool call summaries, and cross-task context
for efficient context injection into subsequent tasks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolSummary:
    """Summarized tool result for context passing."""
    tool_name: str
    summary: str
    success: bool = True


@dataclass
class TaskSummary:
    """Summary of a completed task."""
    task_name: str
    task_index: int
    content: str
    tool_summaries: List[ToolSummary] = field(default_factory=list)
    changes_made: List[str] = field(default_factory=list)


class JobMemory:
    """Tracks mission state across orchestrator tasks.

    Provides efficient context injection by summarizing previous
    task results rather than passing full conversation history.
    """

    def __init__(self, job_id: str):
        self.job_id = job_id
        self._task_summaries: List[TaskSummary] = []
        self._current_task: Optional[str] = None
        self._current_tools: List[ToolSummary] = []

    def on_task_start(self, task_name: str, task_index: int) -> None:
        """Called when a new task begins."""
        self._current_task = task_name
        self._current_tools = []
        logger.debug(f"[JobMemory] Task started: {task_name}")

    def on_tool_result(
        self,
        tool_name: str,
        result: Dict[str, Any],
        args: Optional[Dict[str, Any]] = None,
    ) -> ToolSummary:
        """Summarize a tool result for context passing."""
        if isinstance(result, dict):
            summary = result.get("summary", "")
            if not summary:
                # Auto-generate summary from key fields
                keys_to_check = ["corridor_id", "flight_id", "certificate_id", "status", "score"]
                parts = []
                for k in keys_to_check:
                    if k in result:
                        parts.append(f"{k}={result[k]}")
                summary = ", ".join(parts) if parts else str(result)[:150]
            success = "error" not in result
        else:
            summary = str(result)[:150]
            success = True

        tool_summary = ToolSummary(
            tool_name=tool_name,
            summary=summary[:200],
            success=success,
        )
        self._current_tools.append(tool_summary)
        return tool_summary

    def on_task_complete(self, task_name: str, task_index: int, content: str) -> TaskSummary:
        """Called when a task completes. Extracts and stores summary."""
        # Detect changes made from tool results
        changes = []
        for ts in self._current_tools:
            if ts.success and ts.tool_name in (
                "create_corridor", "start_simulation", "generate_correction",
                "complete_flight", "generate_certificate",
            ):
                changes.append(f"{ts.tool_name}: {ts.summary}")

        summary = TaskSummary(
            task_name=task_name,
            task_index=task_index,
            content=content[:500],
            tool_summaries=self._current_tools.copy(),
            changes_made=changes,
        )
        self._task_summaries.append(summary)
        logger.debug(f"[JobMemory] Task complete: {task_name}, {len(self._current_tools)} tools, {len(changes)} changes")
        return summary

    def get_task_context(self, task_index: int) -> str:
        """Get summarized context from previous tasks."""
        if task_index == 0 or not self._task_summaries:
            return ""

        parts = ["## Mission Context (from previous phases)\n"]
        for ts in self._task_summaries:
            parts.append(f"### Phase {ts.task_index + 1}: {ts.task_name}")
            if ts.changes_made:
                parts.append("Changes: " + "; ".join(ts.changes_made))
            if ts.content:
                parts.append(f"Result: {ts.content[:300]}")
            parts.append("")

        return "\n".join(parts)

    def on_job_complete(self) -> Dict[str, Any]:
        """Called when the entire job completes. Returns summary."""
        total_tools = sum(len(ts.tool_summaries) for ts in self._task_summaries)
        all_changes = []
        for ts in self._task_summaries:
            all_changes.extend(ts.changes_made)

        return {
            "total_tasks": len(self._task_summaries),
            "total_tool_calls": total_tools,
            "changes_made": all_changes,
        }
