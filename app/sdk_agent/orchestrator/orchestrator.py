"""Mission Orchestrator — sequential multi-agent task execution.

Adapted from power-bi-backend-agent-v2 Orchestrator pattern.
Executes mission templates by delegating tasks to specialized agents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from ..agent import CorridorAgent
from agent_framework.composable.agents.events import AgentEvent, AgentEventType
from .templates import get_template, Template, Task

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result from a completed task."""
    task_id: str
    task_name: str
    content: str
    tool_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OrchestratorEvent:
    """Event from orchestrator execution."""
    type: str  # "task_start", "task_complete", "agent_event", "job_complete", "error"
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "data": self.data}


class MissionOrchestrator:
    """Executes multi-task missions using specialized agents.

    Each task in a template runs with its designated agent mode
    (designer, guardian, compliance). Context from previous tasks
    is passed to subsequent tasks.

    Usage:
        orch = MissionOrchestrator(job_id="mission-001")
        async for event in orch.run("full_mission"):
            print(event)
    """

    def __init__(self, job_id: str):
        self.job_id = job_id
        self._task_results: List[TaskResult] = []

    def _build_context_prefix(self, task_index: int) -> str:
        """Build context from previous task results."""
        if task_index == 0 or not self._task_results:
            return ""

        context_parts = ["## Previous Task Results\n"]
        for result in self._task_results:
            context_parts.append(f"### {result.task_name}")
            if result.tool_results:
                context_parts.append("**Tool outputs:**")
                for tr in result.tool_results[-5:]:
                    tool_name = tr.get("tool", "unknown")
                    summary = tr.get("summary", "")
                    if summary:
                        context_parts.append(f"- {tool_name}: {summary[:200]}")
            if result.content:
                preview = result.content[:500]
                if len(result.content) > 500:
                    preview += "..."
                context_parts.append(f"**Summary:** {preview}")
            context_parts.append("")

        context_parts.append("---\n## Current Task\n")
        return "\n".join(context_parts)

    async def run(self, template_id: str) -> AsyncIterator[OrchestratorEvent]:
        """Execute a template's tasks sequentially."""
        template = get_template(template_id)
        if not template:
            yield OrchestratorEvent(
                type="error",
                data={"message": f"Template '{template_id}' not found"},
            )
            return

        logger.info(f"[Orchestrator] Starting: {template.name} ({len(template.tasks)} tasks)")
        self._task_results = []
        total_tasks = len(template.tasks)
        completed = 0

        yield OrchestratorEvent(
            type="job_start",
            data={
                "template_id": template_id,
                "template_name": template.name,
                "total_tasks": total_tasks,
            },
        )

        for idx, task in enumerate(template.tasks):
            yield OrchestratorEvent(
                type="task_start",
                data={
                    "task_index": idx,
                    "task_id": task.id,
                    "task_name": task.name,
                    "agent_mode": task.agent_mode,
                    "total_tasks": total_tasks,
                },
            )

            logger.info(f"[Orchestrator] Task {idx + 1}/{total_tasks}: {task.name} (agent: {task.agent_mode})")

            try:
                # Create agent for this task's mode
                agent = CorridorAgent(
                    job_id=self.job_id,
                    mode=task.agent_mode,
                )

                # Build prompt with context from previous tasks
                context_prefix = self._build_context_prefix(idx)
                full_prompt = f"{context_prefix}\n\n{task.prompt}" if context_prefix else task.prompt

                tool_calls = 0
                tool_results: List[Dict[str, Any]] = []
                final_content = ""

                async for agent_event in agent.run(full_prompt):
                    if agent_event.type == AgentEventType.TOOL_RESULT:
                        tool_calls += 1
                        tool_results.append({
                            "tool": agent_event.data.get("tool", ""),
                            "summary": str(agent_event.data.get("result", ""))[:200],
                            "success": agent_event.data.get("success", True),
                        })

                    if agent_event.type == AgentEventType.CONTENT:
                        final_content = agent_event.data.get("text", "")

                    yield OrchestratorEvent(
                        type="agent_event",
                        data={
                            "task_index": idx,
                            "task_id": task.id,
                            "event_type": agent_event.type.value,
                            "event_data": agent_event.data,
                        },
                    )

                self._task_results.append(TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    content=final_content,
                    tool_results=tool_results,
                ))

                completed += 1
                yield OrchestratorEvent(
                    type="task_complete",
                    data={
                        "task_index": idx,
                        "task_id": task.id,
                        "task_name": task.name,
                        "tool_calls": tool_calls,
                    },
                )

            except Exception as e:
                logger.exception(f"[Orchestrator] Task failed: {e}")
                yield OrchestratorEvent(
                    type="task_error",
                    data={
                        "task_index": idx,
                        "task_id": task.id,
                        "task_name": task.name,
                        "error": str(e),
                    },
                )

        yield OrchestratorEvent(
            type="job_complete",
            data={
                "template_id": template_id,
                "total_tasks": total_tasks,
                "completed_tasks": completed,
            },
        )

        logger.info(f"[Orchestrator] Completed: {completed}/{total_tasks} tasks")
