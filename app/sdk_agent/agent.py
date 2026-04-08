"""Ākāsā Agent Factory — creates agents from the framework using tools and config.

This wires the auto-ai-agent-framework's SingleAgent to our drone tools,
exercising: memory, context assembly, stagnation detection, goal tracking,
token tracking, tool executor — all v2.1 improvements.

Supports two creation modes:
1. Programmatic: CorridorAgent(job_id, mode=...)
2. Config-based: CorridorAgent.from_config(config_path, job_id)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

# Framework imports
from agent_framework.composable.agents.single import SingleAgent, StagnationConfig
from agent_framework.composable.agents.base import AgentConfig
from agent_framework.composable.agents.events import AgentEvent, AgentEventType
from agent_framework.composable.gateways.bedrock import BedrockGateway
from agent_framework.composable.gateways.base import (
    GatewayConfig, GatewayMessage, ToolDefinition, ToolParameter,
)
from agent_framework.composable.memory.three_tier import ThreeTierMemory, MemoryConfig
from agent_framework.composable.context.assembler import ContextAssembler, ContextConfig
from agent_framework.composable.tools.registry import ToolRegistry
from agent_framework.composable.tools.base import Tool, ToolResult as FWToolResult

# v2.1 imports
from agent_framework.composable.tokens.counter import ApproximateTokenCounter
from agent_framework.composable.tokens.tracker import TokenTracker
from agent_framework.composable.memory.summarizer import TrivialSummarizer
from agent_framework.composable.memory.promotion import MemoryPromoter
from agent_framework.composable.agents.stagnation import EnhancedStagnationDetector, EnhancedStagnationConfig
from agent_framework.composable.agents.goal_tracker import GoalTracker, GoalTrackerConfig

# Local tools
from .tools.registry import get_tool_definitions
from .tools.executor import create_tool_executor

logger = logging.getLogger(__name__)


def build_tool_definitions() -> List[ToolDefinition]:
    """Convert our @tool registry to framework ToolDefinition objects."""
    raw_defs = get_tool_definitions()
    tool_defs = []
    for td in raw_defs:
        params = []
        schema = td["input_schema"]
        for pname, pinfo in schema.get("properties", {}).items():
            params.append(ToolParameter(
                name=pname,
                type=pinfo.get("type", "string"),
                description=pinfo.get("description", ""),
                required=pname in schema.get("required", []),
            ))
        tool_defs.append(ToolDefinition(
            name=td["name"],
            description=td["description"],
            parameters=params,
        ))
    return tool_defs


def create_guardian_agent(
    model: str = None,
    max_iterations: int = 40,
    enable_goal_tracking: bool = True,
    enable_stagnation: bool = True,
) -> SingleAgent:
    """Create a Flight Guardian agent using the full framework.

    This exercises ALL v2.1 improvements:
    - ThreeTierMemory with summarizer + promoter
    - ContextAssembler with token budget
    - EnhancedStagnationDetector
    - GoalTracker
    - TokenTracker
    """
    model = model or os.environ.get(
        "GUARDIAN_MODEL", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    )

    # Gateway
    gateway_config = GatewayConfig(
        model=model,
        max_tokens=1024,
        temperature=0.1,
        extra={"region": os.environ.get("AWS_REGION", "us-east-1")},
    )
    gateway = BedrockGateway(gateway_config)

    # Token counter (v2.1)
    token_counter = ApproximateTokenCounter()

    # Memory with summarizer + promoter (v2.1)
    memory_config = MemoryConfig(
        max_messages=40,
        max_tokens=80000,
    )
    memory = ThreeTierMemory(
        config=memory_config,
        summarizer=TrivialSummarizer(),
        promoter=None,  # Will create after memory init
        token_counter=token_counter,
    )
    # Wire promoter
    memory._promoter = MemoryPromoter(memory.long_term)

    # Context assembler with budget (v2.1)
    context_config = ContextConfig(
        max_context_tokens=90000,
        compress_history_threshold=15,
        include_base_context=True,
        include_history_context=True,
        include_error_context=True,
    )
    context = ContextAssembler(
        config=context_config,
        token_counter=token_counter,
    )
    context.set_base_context(
        system_identity=GUARDIAN_SYSTEM_PROMPT,
        capabilities=["drone monitoring", "deviation detection", "correction generation", "compliance recording"],
        constraints=["always check block membership before advancing", "apply corrections immediately on deviation"],
    )

    # Agent config
    agent_config = AgentConfig(
        name="FlightGuardian",
        max_iterations=max_iterations,
        system_prompt=GUARDIAN_SYSTEM_PROMPT,
    )

    # Build tool definitions
    tool_defs = build_tool_definitions()

    # Create agent
    agent = SingleAgent(
        gateway=gateway,
        config=agent_config,
        memory=memory,
        context_assembler=context,
        tools=tool_defs,
        tool_executor=create_tool_executor(),
    )

    return agent


def create_corridor_designer_agent(
    model: str = None,
    max_iterations: int = 10,
) -> SingleAgent:
    """Create a Corridor Designer agent."""
    model = model or os.environ.get(
        "WORKER_MODEL", "qwen.qwen3-vl-235b-a22b"
    )

    gateway_config = GatewayConfig(
        model=model,
        max_tokens=1024,
        temperature=0.1,
        extra={"region": os.environ.get("AWS_REGION", "us-east-1")},
    )
    gateway = BedrockGateway(gateway_config)

    memory = ThreeTierMemory(config=MemoryConfig(max_messages=30))

    context_config = ContextConfig(max_context_tokens=50000)
    context = ContextAssembler(config=context_config)
    context.set_base_context(system_identity=DESIGNER_SYSTEM_PROMPT)

    agent_config = AgentConfig(
        name="CorridorDesigner",
        max_iterations=max_iterations,
        system_prompt=DESIGNER_SYSTEM_PROMPT,
    )

    # Only corridor tools
    corridor_tool_names = {"create_corridor", "list_corridors", "get_corridor_detail", "validate_corridor"}
    tool_defs = [t for t in build_tool_definitions() if t.name in corridor_tool_names]

    return SingleAgent(
        gateway=gateway,
        config=agent_config,
        memory=memory,
        context_assembler=context,
        tools=tool_defs,
        tool_executor=create_tool_executor(),
    )


def create_compliance_agent(
    model: str = None,
    max_iterations: int = 8,
) -> SingleAgent:
    """Create a Compliance Recorder agent."""
    model = model or os.environ.get(
        "WORKER_MODEL", "qwen.qwen3-vl-235b-a22b"
    )

    gateway_config = GatewayConfig(
        model=model,
        max_tokens=1024,
        temperature=0.1,
        extra={"region": os.environ.get("AWS_REGION", "us-east-1")},
    )
    gateway = BedrockGateway(gateway_config)

    memory = ThreeTierMemory(config=MemoryConfig(max_messages=20))

    context = ContextAssembler(config=ContextConfig(max_context_tokens=50000))
    context.set_base_context(system_identity=COMPLIANCE_SYSTEM_PROMPT)

    agent_config = AgentConfig(
        name="ComplianceRecorder",
        max_iterations=max_iterations,
        system_prompt=COMPLIANCE_SYSTEM_PROMPT,
    )

    compliance_tool_names = {
        "get_flight_events", "verify_chain_integrity",
        "calculate_conformance_score", "generate_certificate",
        "get_flight_telemetry",
    }
    tool_defs = [t for t in build_tool_definitions() if t.name in compliance_tool_names]

    return SingleAgent(
        gateway=gateway,
        config=agent_config,
        memory=memory,
        context_assembler=context,
        tools=tool_defs,
        tool_executor=create_tool_executor(),
    )


# =============================================================================
# System Prompts
# =============================================================================

GUARDIAN_SYSTEM_PROMPT = """You are the Ākāsā Flight Supervisor AI. The drone flies autonomously along a digital rail with its own autopilot. It encounters random environmental disruptions (wind gusts, GPS noise, turbulence) and self-corrects automatically.

## Your Role: READ-ONLY MONITORING with selective intervention
The drone moves on its own — you do NOT need to step it or manually correct it.

## Monitoring Loop
1. Call check_block_membership or get_drone_position to observe the drone's current state
2. Call get_environment_state to see current wind, GPS noise, and turbulence conditions
3. Call get_flight_telemetry for a full status snapshot with conformance score
4. Wait a moment between observations to let the drone advance

## When to Intervene
- If deviation is consistently high (>50m), call set_correction_strength with a higher value (0.5-0.8)
- If conditions are extreme and deviation is dangerous (>200m), call emergency_land
- If you want to test the drone, you can inject_wind_gust or inject_gps_noise manually

## Mission Completion
- When the drone reaches the end (status=COMPLETE), or after sufficient monitoring, call complete_flight
- Then verify chain integrity and generate a compliance certificate

## Key Rules
- Do NOT call step_simulation — the drone advances automatically
- Do NOT call generate_correction — the autopilot handles this
- Focus on observing, reporting, and intervening only when needed
- Provide brief reasoning for each observation (1-2 sentences)
"""

DESIGNER_SYSTEM_PROMPT = """You are the Ākāsā Corridor Designer. You create and validate aerial corridors.

## Process
1. Use create_corridor to define a new corridor between two points
2. Use validate_corridor to verify safety parameters
3. Report the corridor details including block count and estimated distance

## Guidelines
- Use H3 resolution 10 (65m cells) for standard corridors
- Use resolution 9 (174m cells) for long-distance corridors
- Always validate after creation
"""

COMPLIANCE_SYSTEM_PROMPT = """You are the Ākāsā Compliance Recorder. You verify flight data integrity and generate compliance certificates.

## Process
1. Use get_flight_events to retrieve the flight's event log
2. Use verify_chain_integrity to confirm the hash chain is valid
3. Use calculate_conformance_score to compute the compliance ratio
4. Use generate_certificate to produce the official Compliance Certificate

## Certificate Interpretation
- Score >= 0.95: Excellent compliance
- Score 0.80-0.95: Acceptable with minor deviations
- Score < 0.80: Needs review — significant corridor departures
"""

COORDINATOR_SYSTEM_PROMPT = """You are the Ākāsā Mission Coordinator. You manage drone corridor missions end-to-end.

## Mission Workflow
1. **Corridor Design**: Create a digital rail between two points using create_corridor, then validate_corridor
2. **Flight Launch**: Call start_simulation — the drone flies AUTOMATICALLY with its own autopilot. Random wind, GPS noise, and turbulence affect it realistically. The autopilot self-corrects.
3. **Monitoring**: Observe the flight by calling check_block_membership and get_drone_position periodically. The drone is moving on its own — just read its state. You can call get_environment_state to see conditions.
4. **Intervention** (only if needed): Use set_correction_strength to tune autopilot. Use emergency_land if critically unsafe.
5. **Completion**: When drone reaches the end (or after sufficient monitoring), call complete_flight, verify_chain_integrity, calculate_conformance_score, and generate_certificate.

## Key Rules
- Do NOT call step_simulation — the drone advances automatically in the background
- Do NOT call generate_correction — the autopilot handles corrections
- Wait a moment between observations to let the drone advance
- Keep observations brief and report status concisely
"""

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "agents" / "sdk_agent.yaml"


class CorridorAgent:
    """Unified agent wrapper for Akasa Corridor operations.

    Adapted from PowerBIAgent pattern in power-bi-backend-agent-v2.
    Supports single-agent mode (all tools) and multi-agent mode (orchestrated).
    """

    def __init__(
        self,
        job_id: str,
        mode: str = "single",
        model: str = None,
        max_iterations: int = 40,
    ):
        self.job_id = job_id
        self.mode = mode  # "single", "guardian", "designer", "compliance"

        if mode == "guardian":
            self.agent = create_guardian_agent(model=model, max_iterations=max_iterations)
        elif mode == "designer":
            self.agent = create_corridor_designer_agent(model=model, max_iterations=max_iterations)
        elif mode == "compliance":
            self.agent = create_compliance_agent(model=model, max_iterations=max_iterations)
        else:
            # Single agent with all tools (default for API use)
            self.agent = self._create_single_agent(model=model, max_iterations=max_iterations)

        logger.info(f"[CorridorAgent] Created: mode={mode}, job_id={job_id}")

    def _create_single_agent(self, model: str = None, max_iterations: int = 40) -> SingleAgent:
        """Create a single agent with all tools (standalone mode)."""
        model = model or os.environ.get("LLM_MODEL", "global.anthropic.claude-haiku-4-5-20251001-v1:0")

        gateway_config = GatewayConfig(
            model=model,
            max_tokens=2048,
            temperature=0.1,
            extra={"region": os.environ.get("AWS_REGION", "us-east-1")},
        )
        gateway = BedrockGateway(gateway_config)

        memory = ThreeTierMemory(config=MemoryConfig(max_messages=50, session_id=self.job_id))

        agent_config = AgentConfig(
            agent_id=f"corridor-{self.job_id}",
            name="AkasaCorridorAgent",
            max_iterations=max_iterations,
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
        )

        tool_defs = build_tool_definitions()

        return SingleAgent(
            gateway=gateway,
            config=agent_config,
            memory=memory,
            tools=tool_defs,
            tool_executor=create_tool_executor(job_id=self.job_id),
            stagnation_config=StagnationConfig(max_tool_calls_before_prompt=30),
        )

    async def run(self, user_message: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with a user message, yielding events."""
        async for event in self.agent.run(user_message):
            yield event

    async def run_to_completion(self, user_message: str) -> Dict[str, Any]:
        """Run the agent and return the final result."""
        result = await self.agent.run_to_completion(user_message)
        return {
            "content": result.content,
            "success": result.success,
            "iterations": result.iterations,
            "duration_s": result.duration_seconds,
            "tool_calls": result.tool_calls,
            "usage": result.usage.to_dict() if result.usage else None,
        }

    def reset(self) -> None:
        """Reset the agent for a new conversation."""
        self.agent.reset()

    @classmethod
    def from_config(
        cls,
        job_id: str,
        config_path: Optional[str] = None,
    ) -> "CorridorAgent":
        """Create CorridorAgent from YAML configuration."""
        try:
            from agent_framework.composable import ConfigLoader
        except ImportError:
            logger.warning("Config loading not available. Using programmatic creation.")
            return cls(job_id=job_id)

        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        if not path.exists():
            logger.warning(f"Config not found: {path}. Using programmatic creation.")
            return cls(job_id=job_id)

        loader = ConfigLoader()
        config = loader.load(path)

        os.environ["JOB_ID"] = job_id

        tool_defs = build_tool_definitions()

        agent = SingleAgent.from_config(
            config=config,
            tool_executor=create_tool_executor(job_id=job_id),
            tool_definitions=tool_defs,
        )

        instance = cls.__new__(cls)
        instance.job_id = job_id
        instance.mode = "config"
        instance.agent = agent

        logger.info(f"[CorridorAgent] Created from config: {path}")
        return instance
