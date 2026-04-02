"""Real LLM integration test — Full drone flight with Guardian Agent.

This test:
1. Creates a corridor (Delhi → Agra)
2. Starts a simulation
3. Runs the Flight Guardian agent with real LLM (Bedrock Haiku)
4. The LLM uses tools to monitor the drone, detect deviations, apply corrections
5. Verifies compliance certificate at the end

Requires: AWS credentials in environment, Bedrock access.
Run: python tests/test_real_llm_flight.py
"""

import asyncio
import json
import os
import sys
import time

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/autoai-mini/Documents/axplusb/auto-ai-agent-framework/agent-framework-pypi/src')

# Set env
os.environ['AWS_REGION'] = 'us-east-1'
# AWS credentials from environment (set in .env or export)
assert os.environ.get('AWS_ACCESS_KEY_ID'), "Set AWS_ACCESS_KEY_ID in environment"
assert os.environ.get('AWS_SECRET_ACCESS_KEY'), "Set AWS_SECRET_ACCESS_KEY in environment"

# Import tools (triggers registration)
from app.sdk_agent.tools.simulation import drone_tools
from app.sdk_agent.tools.corridor import management
from app.sdk_agent.tools.compliance import ledger_tools
from app.sdk_agent.tools.registry import execute_tool, get_tool_definitions

# Import framework
from agent_framework.composable.gateways.bedrock import BedrockGateway
from agent_framework.composable.gateways.base import (
    GatewayConfig, GatewayMessage, ToolDefinition, ToolParameter,
    ToolUseBlock, TextBlock, StopReason, GatewayResponse,
)
from agent_framework.composable.gateways.base import ToolResult as GatewayToolResult


SYSTEM_PROMPT = """You are the Ākāsā Flight Guardian AI. You monitor a simulated drone flying along a digital rail (an ordered sequence of geocode blocks).

## Your Mission
Execute a complete flight monitoring cycle:
1. First, check the drone's block membership using check_block_membership
2. If the drone is NOMINAL (in assigned block), advance the simulation with step_simulation
3. If the drone is DEVIATING, apply a correction with generate_correction, then step again
4. After monitoring a few cycles, get the full telemetry with get_flight_telemetry
5. When you've monitored enough cycles (5-8 steps), complete the flight
6. Finally, generate the compliance certificate

## Important
- Always check block_membership BEFORE stepping
- If deviation is detected, correct BEFORE stepping
- Provide brief reasoning for each action
- Complete the flight when you've done enough monitoring cycles
"""


async def run_guardian_flight():
    """Run a complete flight with real LLM Guardian."""

    print("=" * 60)
    print("ĀKĀSĀ FLIGHT GUARDIAN — Real LLM Integration Test")
    print("=" * 60)

    # Step 1: Create corridor
    print("\n--- Step 1: Creating corridor (Delhi → Agra) ---")
    corridor_result = execute_tool("create_corridor", {
        "name": "Delhi-Agra Express",
        "start_lat": 28.6139,
        "start_lon": 77.2090,
        "end_lat": 27.1767,
        "end_lon": 78.0081,
        "resolution": 10,
    })
    corridor_id = corridor_result["corridor_id"]
    print(f"  Corridor: {corridor_id} ({corridor_result['block_count']} blocks)")

    # Step 2: Start simulation
    print("\n--- Step 2: Starting simulation ---")
    sim_result = execute_tool("start_simulation", {
        "corridor_id": corridor_id,
        "speed_mps": 20.0,
    })
    flight_id = sim_result["flight_id"]
    print(f"  Flight: {flight_id}")

    # Step 3: Inject some wind to make it interesting
    print("\n--- Step 3: Injecting wind gust ---")
    wind_result = execute_tool("inject_wind_gust", {
        "direction_deg": 90.0,
        "speed_mps": 5.0,
    })
    print(f"  Wind: {wind_result['message']}")

    # Step 4: Run Guardian Agent with real LLM
    print("\n--- Step 4: Running Guardian Agent (Claude Haiku on Bedrock) ---")

    config = GatewayConfig(
        model='global.anthropic.claude-haiku-4-5-20251001-v1:0',
        max_tokens=1024,
        temperature=0.1,
        extra={'region': 'us-east-1'},
    )
    gateway = BedrockGateway(config)

    # Build tool definitions from registry
    tool_defs_raw = get_tool_definitions()
    tool_defs = []
    for td in tool_defs_raw:
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

    # Agent loop
    messages = [
        GatewayMessage(
            role="user",
            content=f"Monitor flight {flight_id} on corridor {corridor_id}. Run 5 monitoring cycles, then complete the flight and generate the compliance certificate.",
        ),
    ]

    total_input_tokens = 0
    total_output_tokens = 0
    iteration = 0
    max_iterations = 15

    while iteration < max_iterations:
        iteration += 1
        print(f"\n  [Iteration {iteration}]")

        # Call LLM
        response = await gateway.invoke(
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=tool_defs,
        )
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Process response
        tool_calls = []
        for block in response.content:
            if isinstance(block, TextBlock) and block.text:
                print(f"    Guardian: {block.text[:200]}")
            elif isinstance(block, ToolUseBlock):
                tool_calls.append(block)
                print(f"    Tool: {block.name}({json.dumps(block.input)[:100]})")

        # Add assistant response to messages
        messages.append(GatewayMessage(role="assistant", content=response.content))

        # If no tool calls, agent is done
        if response.stop_reason != StopReason.TOOL_USE or not tool_calls:
            print(f"    → Agent finished (stop_reason: {response.stop_reason})")
            break

        # Execute tools
        tool_results = []
        for tc in tool_calls:
            result = execute_tool(tc.name, tc.input)
            # Print key info
            if "error" in result:
                print(f"    → {tc.name} ERROR: {result['error'][:100]}")
            elif tc.name == "check_block_membership":
                print(f"    → Status: {result.get('status')}, deviation: {result.get('deviation_meters')}m")
            elif tc.name == "step_simulation":
                print(f"    → Step {result.get('step')}: block {result.get('block_index')}/{result.get('total_blocks')}")
            elif tc.name == "generate_certificate":
                print(f"    → Certificate: {result.get('certificate_id')}, score: {result.get('corridor_conformance_score')}")

            tool_results.append(GatewayToolResult(
                tool_use_id=tc.id,
                content=json.dumps(result),
                is_error="error" in result,
            ))

        # Add tool results to messages
        messages.append(GatewayMessage(role="user", content=tool_results))

    # Step 5: Summary
    print("\n" + "=" * 60)
    print("FLIGHT SUMMARY")
    print("=" * 60)
    print(f"  Iterations: {iteration}")
    print(f"  Input tokens: {total_input_tokens:,}")
    print(f"  Output tokens: {total_output_tokens:,}")
    print(f"  Total tokens: {total_input_tokens + total_output_tokens:,}")

    # Get final telemetry
    telemetry = execute_tool("get_flight_telemetry", {})
    print(f"  Flight status: {telemetry.get('status')}")
    print(f"  Progress: {telemetry.get('progress_percent')}%")
    print(f"  Conformance: {telemetry.get('conformance_score')}")
    print(f"  Total events: {telemetry.get('total_events')}")
    print(f"  Deviations: {telemetry.get('deviations')}")

    # Verify chain integrity
    integrity = execute_tool("verify_chain_integrity", {})
    print(f"  Chain integrity: {'VALID' if integrity.get('valid') else 'INVALID'}")

    print("\nTest complete!")
    return True


if __name__ == "__main__":
    asyncio.run(run_guardian_flight())
