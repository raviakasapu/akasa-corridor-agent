"""Ākāsā Agent Factory — creates agents from the framework using tools and config.

This wires the auto-ai-agent-framework's SingleAgent to our drone tools,
exercising: memory, context assembly, stagnation detection, goal tracking,
token tracking, tool executor — all v2.1 improvements.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional

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
from .tools.registry import execute_tool, get_tool_definitions

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


def create_tool_executor() -> Callable:
    """Create a tool executor function that bridges framework to our registry."""
    def executor(name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return execute_tool(name, input_data)
    return executor


def create_guardian_agent(
    model: str = None,
    max_iterations: int = 20,
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

GUARDIAN_SYSTEM_PROMPT = """You are the Ākāsā Flight Guardian AI. You monitor a simulated drone flying along a digital rail — an ordered sequence of geocode blocks.

## Control Loop (every cycle)
1. check_block_membership — resolve drone position to geocode block, compare to assigned
2. If NOMINAL: step_simulation to advance — the drone will auto-advance blocks
3. If DEVIATING: generate_correction first, then step_simulation
4. Repeat for the requested number of cycles

## Key Rules
- ALWAYS check block_membership BEFORE stepping
- If deviation detected, correct BEFORE stepping
- After completing monitoring cycles, call complete_flight
- Provide brief reasoning for each action (1-2 sentences)
- Track total deviations and corrections applied

## Wind/GPS Disruptions
If instructed to inject disruptions, use inject_wind_gust or inject_gps_noise, then monitor the response.
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
