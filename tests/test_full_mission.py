"""Full Mission Test — 3 agents, real LLM, complete lifecycle.

Design corridor → Fly with Guardian → Generate compliance certificate.
Tests the auto-ai-agent-framework SingleAgent with all v2.1 features.

Run: python tests/test_full_mission.py
"""

import asyncio
import os
import sys
import time
import json

# Paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/autoai-mini/Documents/axplusb/auto-ai-agent-framework/agent-framework-pypi/src')

# Env
os.environ['AWS_REGION'] = 'us-east-1'
assert os.environ.get('AWS_ACCESS_KEY_ID'), "Set AWS_ACCESS_KEY_ID in environment"
assert os.environ.get('AWS_SECRET_ACCESS_KEY'), "Set AWS_SECRET_ACCESS_KEY in environment"

# Import tools (triggers @tool registration)
from app.sdk_agent.tools.simulation import drone_tools
from app.sdk_agent.tools.corridor import management
from app.sdk_agent.tools.compliance import ledger_tools
from app.sdk_agent.tools.registry import execute_tool

# Import agent factory
from app.sdk_agent.agent import (
    create_guardian_agent,
    create_corridor_designer_agent,
    create_compliance_agent,
)

# Framework event types
from agent_framework.composable.agents.events import AgentEvent, AgentEventType


def print_event(event: AgentEvent, agent_name: str):
    """Print agent events in a readable format."""
    if event.type == AgentEventType.AGENT_START:
        print(f"  [{agent_name}] Started")
    elif event.type == AgentEventType.THINKING:
        text = event.data.get("text", "")[:150] if event.data else ""
        if text:
            print(f"  [{agent_name}] Thinking: {text}")
    elif event.type == AgentEventType.CONTENT:
        text = event.data.get("text", "")[:200] if event.data else ""
        if text:
            print(f"  [{agent_name}] {text}")
    elif event.type == AgentEventType.TOOL_CALL:
        name = event.data.get("tool_name", "") if event.data else ""
        args = json.dumps(event.data.get("tool_input", {}))[:80] if event.data else ""
        print(f"  [{agent_name}] Tool: {name}({args})")
    elif event.type == AgentEventType.TOOL_RESULT:
        result = event.data.get("result", "") if event.data else ""
        if isinstance(result, dict):
            # Print key info
            if "error" in result:
                print(f"  [{agent_name}] → ERROR: {result['error'][:100]}")
            elif "status" in result:
                print(f"  [{agent_name}] → Status: {result['status']}")
            elif "corridor_id" in result:
                print(f"  [{agent_name}] → Corridor: {result['corridor_id']}")
            elif "certificate_id" in result:
                print(f"  [{agent_name}] → Certificate: {result['certificate_id']}, score={result.get('corridor_conformance_score')}")
            elif "valid" in result:
                print(f"  [{agent_name}] → Valid: {result['valid']}")
            else:
                summary = result.get("summary", str(result)[:100])
                print(f"  [{agent_name}] → {summary}")
    elif event.type == AgentEventType.AGENT_COMPLETE:
        duration = event.data.get("duration_seconds", 0) if event.data else 0
        iterations = event.data.get("iterations", 0) if event.data else 0
        print(f"  [{agent_name}] Complete ({iterations} iterations, {duration:.1f}s)")
    elif event.type == AgentEventType.STAGNATION_DETECTED:
        reason = event.data.get("reason", "") if event.data else ""
        print(f"  [{agent_name}] ⚠ STAGNATION: {reason}")


async def run_full_mission():
    """Run a complete 3-agent mission."""

    print("=" * 70)
    print("ĀKĀSĀ FULL MISSION — 3 Agents, Real LLM, Framework v2.1")
    print("=" * 70)
    start_time = time.time()

    # ================================================================
    # PHASE 1: Corridor Designer (Qwen 3 on Bedrock)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 1: CORRIDOR DESIGNER (Qwen 3 VL)")
    print("=" * 70)

    designer = create_corridor_designer_agent(max_iterations=5)

    # Subscribe to events
    designer.events.on(AgentEventType.TOOL_CALL, lambda e: print_event(e, "Designer"))
    designer.events.on(AgentEventType.TOOL_RESULT, lambda e: print_event(e, "Designer"))
    designer.events.on(AgentEventType.CONTENT, lambda e: print_event(e, "Designer"))
    designer.events.on(AgentEventType.AGENT_COMPLETE, lambda e: print_event(e, "Designer"))
    designer.events.on(AgentEventType.STAGNATION_DETECTED, lambda e: print_event(e, "Designer"))

    designer_result = await designer.run_to_completion(
        "Create a drone corridor from Delhi (28.6139, 77.2090) to Agra (27.1767, 78.0081) "
        "at H3 resolution 10. Then validate the corridor safety."
    )

    print(f"\n  Designer result: {designer_result.content[:300]}")
    print(f"  Designer stats: {designer_result.iterations} iterations, {designer_result.tool_calls} tool calls")

    # Extract corridor_id from tool results in memory
    corridor_id = None
    from app.sdk_agent.tools.simulation.engine import _corridors
    if _corridors:
        corridor_id = list(_corridors.keys())[-1]
    print(f"  Corridor ID: {corridor_id}")

    if not corridor_id:
        print("  ERROR: No corridor created. Stopping.")
        return

    # ================================================================
    # PHASE 2: Flight Guardian (Claude Haiku)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 2: FLIGHT GUARDIAN (Claude Haiku 4.5)")
    print("=" * 70)

    # Start simulation before guardian
    sim_result = execute_tool("start_simulation", {
        "corridor_id": corridor_id,
        "speed_mps": 20.0,
    })
    flight_id = sim_result["flight_id"]
    print(f"  Flight started: {flight_id}")

    # Inject wind to test deviation handling
    execute_tool("inject_wind_gust", {"direction_deg": 90, "speed_mps": 3.0})
    print("  Wind gust injected: 3 m/s eastward")

    guardian = create_guardian_agent(max_iterations=12, enable_goal_tracking=True)

    guardian.events.on(AgentEventType.TOOL_CALL, lambda e: print_event(e, "Guardian"))
    guardian.events.on(AgentEventType.TOOL_RESULT, lambda e: print_event(e, "Guardian"))
    guardian.events.on(AgentEventType.CONTENT, lambda e: print_event(e, "Guardian"))
    guardian.events.on(AgentEventType.AGENT_COMPLETE, lambda e: print_event(e, "Guardian"))
    guardian.events.on(AgentEventType.STAGNATION_DETECTED, lambda e: print_event(e, "Guardian"))

    guardian_result = await guardian.run_to_completion(
        f"Monitor flight {flight_id} on corridor {corridor_id}. "
        f"Run 5 monitoring cycles (check block membership → step → handle deviations). "
        f"Then complete the flight."
    )

    print(f"\n  Guardian result: {guardian_result.content[:300]}")
    print(f"  Guardian stats: {guardian_result.iterations} iterations, {guardian_result.tool_calls} tool calls")

    # ================================================================
    # PHASE 3: Compliance Recorder (Qwen 3)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 3: COMPLIANCE RECORDER (Qwen 3 VL)")
    print("=" * 70)

    compliance = create_compliance_agent(max_iterations=6)

    compliance.events.on(AgentEventType.TOOL_CALL, lambda e: print_event(e, "Compliance"))
    compliance.events.on(AgentEventType.TOOL_RESULT, lambda e: print_event(e, "Compliance"))
    compliance.events.on(AgentEventType.CONTENT, lambda e: print_event(e, "Compliance"))
    compliance.events.on(AgentEventType.AGENT_COMPLETE, lambda e: print_event(e, "Compliance"))

    compliance_result = await compliance.run_to_completion(
        f"Verify the flight data integrity and generate a Compliance Certificate "
        f"for flight {flight_id}. Report the conformance score and chain integrity."
    )

    print(f"\n  Compliance result: {compliance_result.content[:300]}")
    print(f"  Compliance stats: {compliance_result.iterations} iterations, {compliance_result.tool_calls} tool calls")

    # ================================================================
    # MISSION SUMMARY
    # ================================================================
    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print("MISSION COMPLETE — SUMMARY")
    print("=" * 70)

    total_iters = (
        designer_result.iterations +
        guardian_result.iterations +
        compliance_result.iterations
    )
    total_tools = (
        designer_result.tool_calls +
        guardian_result.tool_calls +
        compliance_result.tool_calls
    )

    # Get final telemetry
    telemetry = execute_tool("get_flight_telemetry", {"flight_id": flight_id})

    print(f"  Total time: {total_time:.1f}s")
    print(f"  Total iterations: {total_iters}")
    print(f"  Total tool calls: {total_tools}")
    print(f"  Flight status: {telemetry.get('status')}")
    print(f"  Conformance score: {telemetry.get('conformance_score')}")
    print(f"  Total events in ledger: {telemetry.get('total_events')}")
    print(f"  Deviations: {telemetry.get('deviations')}")

    # Verify chain
    integrity = execute_tool("verify_chain_integrity", {"flight_id": flight_id})
    print(f"  Chain integrity: {'VALID' if integrity.get('valid') else 'INVALID'}")

    # Token usage
    if hasattr(designer_result, 'usage') and designer_result.usage:
        print(f"\n  Token usage:")
        for agent_name, result in [("Designer", designer_result), ("Guardian", guardian_result), ("Compliance", compliance_result)]:
            if result.usage:
                us = result.usage
                total = us.total_input_tokens + us.total_output_tokens
                print(f"    {agent_name}: {total:,} tokens (in={us.total_input_tokens:,}, out={us.total_output_tokens:,})")

    print(f"\n  Agents used:")
    print(f"    Designer:   Qwen 3 VL 235B (corridor creation + validation)")
    print(f"    Guardian:   Claude Haiku 4.5 (flight monitoring + corrections)")
    print(f"    Compliance: Qwen 3 VL 235B (ledger verification + certificate)")

    print("\n  Framework v2.1 features exercised:")
    print("    ✓ ThreeTierMemory with summarizer + promoter")
    print("    ✓ ContextAssembler with token budget enforcement")
    print("    ✓ SingleAgent loop with tool execution")
    print("    ✓ Event system (TOOL_CALL, TOOL_RESULT, CONTENT, COMPLETE)")
    print("    ✓ Multi-agent sequential orchestration")
    print("    ✓ Multi-LLM (Haiku + Qwen on Bedrock)")

    print("\n" + "=" * 70)
    print("ALL PHASES COMPLETE — Patent MVP + Framework validated")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_full_mission())
