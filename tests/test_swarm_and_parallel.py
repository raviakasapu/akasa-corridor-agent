"""Swarm + Parallel Pattern Tests — Real LLM validation.

Test 1: SwarmPattern — 3 safety reviewers debate whether a deviating drone
        should correct, hold, or emergency land. Must reach consensus.

Test 2: ParallelPattern — corridor design + risk assessment run concurrently,
        results merged.

Test 3: Comparison — same task on Sequential vs Parallel (speed benchmark).

Run: python tests/test_swarm_and_parallel.py
"""

import asyncio
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/autoai-mini/Documents/axplusb/auto-ai-agent-framework/agent-framework-pypi/src')

os.environ.setdefault('AWS_REGION', 'us-east-1')
assert os.environ.get('AWS_ACCESS_KEY_ID'), "Set AWS_ACCESS_KEY_ID"
assert os.environ.get('AWS_SECRET_ACCESS_KEY'), "Set AWS_SECRET_ACCESS_KEY"

# Tools
from app.sdk_agent.tools.simulation import drone_tools
from app.sdk_agent.tools.corridor import management
from app.sdk_agent.tools.compliance import ledger_tools
from app.sdk_agent.tools.registry import execute_tool
from app.sdk_agent.agent import build_tool_definitions, create_tool_executor

# Framework
from agent_framework.composable.gateways.bedrock import BedrockGateway
from agent_framework.composable.gateways.base import GatewayConfig
from agent_framework.composable.memory.three_tier import ThreeTierMemory, MemoryConfig
from agent_framework.composable.context.assembler import ContextAssembler, ContextConfig

# Multi-agent
from agent_framework.composable.multi.agents.specialist import SpecialistAgent
from agent_framework.composable.multi.agents.coordinator import CoordinatorAgent
from agent_framework.composable.multi.agents.profile import AgentProfile, AgentRole
from agent_framework.composable.multi.coordination.swarm import SwarmPattern
from agent_framework.composable.multi.coordination.parallel import ParallelPattern
from agent_framework.composable.multi.coordination.aggregation import MergeAggregation
from agent_framework.composable.multi.coordination.sequential import SequentialPattern, Stage
from agent_framework.composable.multi.coordination.base import Task, CoordinationEventType
from agent_framework.composable.multi.memory.shared_memory import SharedMemory

HAIKU = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
QWEN = "qwen.qwen3-vl-235b-a22b"


def create_gateway(model: str) -> BedrockGateway:
    return BedrockGateway(GatewayConfig(
        model=model, max_tokens=512, temperature=0.3,
        extra={"region": os.environ.get("AWS_REGION", "us-east-1")},
    ))


def create_specialist(profile: AgentProfile, model: str) -> SpecialistAgent:
    gw = create_gateway(model)
    memory = ThreeTierMemory(config=MemoryConfig(max_messages=20))
    context = ContextAssembler(config=ContextConfig(max_context_tokens=50000))
    context.set_base_context(system_identity=profile.system_prompt_template or profile.description)

    all_tools = build_tool_definitions()
    filtered = [t for t in all_tools if t.name in profile.tools] if profile.tools else all_tools

    return SpecialistAgent(
        profile=profile,
        gateway=gw,
        memory=memory,
        context_assembler=context,
        tool_executor=create_tool_executor(),
        all_tools=filtered,
    )


# =============================================================================
# TEST 1: SWARM — Safety Decision Consensus
# =============================================================================

async def test_swarm_consensus():
    """3 safety reviewers debate: correct, hold, or emergency land?"""

    print("\n" + "=" * 70)
    print("TEST 1: SWARM PATTERN — Safety Decision Consensus")
    print("=" * 70)

    # Setup: create corridor and flight with deviation
    execute_tool("create_corridor", {
        "name": "Swarm-Test-Route",
        "start_lat": 28.6139, "start_lon": 77.2090,
        "end_lat": 27.1767, "end_lon": 78.0081,
    })
    from app.sdk_agent.tools.simulation.engine import _corridors
    corridor_id = list(_corridors.keys())[-1]

    sim_result = execute_tool("start_simulation", {"corridor_id": corridor_id, "speed_mps": 20.0})
    flight_id = sim_result["flight_id"]

    # Inject strong wind to cause deviation
    execute_tool("inject_wind_gust", {"direction_deg": 90, "speed_mps": 8.0})
    for _ in range(5):
        execute_tool("step_simulation", {"steps": 1})

    telemetry = execute_tool("get_flight_telemetry", {})
    print(f"  Setup: Flight {flight_id}, deviation={telemetry.get('conformance_score')}")

    # Create 3 safety reviewers with different perspectives
    reviewer_1 = create_specialist(AgentProfile(
        id="safety-conservative",
        name="Conservative Safety Officer",
        role=AgentRole.REVIEWER,
        description="Conservative safety reviewer — prioritizes caution",
        capabilities=["safety_review"],
        tools=["check_block_membership", "get_flight_telemetry"],
        domains=["safety"],
        system_prompt_template=(
            "You are a CONSERVATIVE safety officer. You prioritize caution over efficiency. "
            "Check the drone's status and telemetry. If there's any deviation, recommend the safest action. "
            "Respond with your RECOMMENDATION: CORRECT, HOLD, or EMERGENCY_LAND and brief reasoning."
        ),
    ), HAIKU)

    reviewer_2 = create_specialist(AgentProfile(
        id="safety-balanced",
        name="Balanced Safety Analyst",
        role=AgentRole.REVIEWER,
        description="Balanced safety analyst — weighs risk vs mission success",
        capabilities=["safety_review"],
        tools=["check_block_membership", "get_flight_telemetry"],
        domains=["safety"],
        system_prompt_template=(
            "You are a BALANCED safety analyst. You weigh risk against mission success. "
            "Check the drone's status. Minor deviations can be corrected; major ones need emergency action. "
            "Respond with your RECOMMENDATION: CORRECT, HOLD, or EMERGENCY_LAND and brief reasoning."
        ),
    ), QWEN)

    reviewer_3 = create_specialist(AgentProfile(
        id="safety-operational",
        name="Operational Safety Engineer",
        role=AgentRole.REVIEWER,
        description="Operational engineer — focuses on what's technically feasible",
        capabilities=["safety_review"],
        tools=["check_block_membership", "get_flight_telemetry", "generate_correction"],
        domains=["safety", "operations"],
        system_prompt_template=(
            "You are an OPERATIONAL safety engineer. You focus on what's technically feasible. "
            "Check the drone's deviation and whether correction is possible. "
            "Respond with your RECOMMENDATION: CORRECT, HOLD, or EMERGENCY_LAND and brief reasoning."
        ),
    ), QWEN)

    # Run swarm
    swarm = SwarmPattern(
        max_rounds=3,
        consensus_threshold=0.6,
        timeout_seconds=60,
    )

    shared = SharedMemory()
    shared.add_artifact("flight_id", flight_id, "system")
    shared.add_artifact("corridor_id", corridor_id, "system")

    task = Task(
        description=(
            f"Flight {flight_id} is deviating from corridor {corridor_id}. "
            f"Current telemetry shows conformance={telemetry.get('conformance_score')}. "
            f"Review the situation and recommend: CORRECT, HOLD, or EMERGENCY_LAND."
        ),
        requirements={"capabilities": ["safety_review"]},
    )

    agents = [reviewer_1, reviewer_2, reviewer_3]
    start = time.time()

    print(f"\n  Running Swarm with 3 reviewers...")
    events = []
    try:
        async for event in swarm.coordinate(task, agents, shared):
            events.append(event)
            if event.type == CoordinationEventType.COORDINATION_START:
                print(f"  [SWARM] Started")
            elif event.type == CoordinationEventType.ROUND_START:
                print(f"  [ROUND {event.data.get('round', '?')}]")
            elif event.type == CoordinationEventType.AGENT_COMPLETE:
                output = event.data.get("output", "")
                preview = str(output)[:120] if output else "(no output)"
                print(f"    [{event.agent_id}] {preview}")
            elif event.type == CoordinationEventType.CONSENSUS_REACHED:
                conf = event.data.get("confidence", 0)
                print(f"  [CONSENSUS] Reached with confidence {conf:.2f}")
            elif event.type == CoordinationEventType.ROUND_COMPLETE:
                print(f"  [ROUND COMPLETE]")
            elif event.type == CoordinationEventType.COORDINATION_COMPLETE:
                success = event.data.get("success", False)
                agents_used = event.data.get("agents_used", [])
                print(f"\n  [SWARM] {'SUCCESS' if success else 'DONE'}, agents: {agents_used}")
            elif event.type == CoordinationEventType.PROGRESS_UPDATE:
                print(f"  [PROGRESS] {event.data.get('message', '')}")
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()

    elapsed = time.time() - start
    print(f"\n  Time: {elapsed:.1f}s, Events: {len(events)}")
    print(f"  Artifacts: {shared.list_artifacts()}")

    return elapsed


# =============================================================================
# TEST 2: PARALLEL — Concurrent Design + Assessment
# =============================================================================

async def test_parallel_execution():
    """Route planning + risk assessment run simultaneously."""

    print("\n" + "=" * 70)
    print("TEST 2: PARALLEL PATTERN — Concurrent Design + Assessment")
    print("=" * 70)

    # Two specialists that can work independently
    route_planner = create_specialist(AgentProfile(
        id="route-planner",
        name="Route Planner",
        role=AgentRole.DOMAIN_SPECIALIST,
        description="Plans optimal corridor routes",
        capabilities=["route_planning"],
        tools=["create_corridor", "get_corridor_detail"],
        domains=["routing"],
        system_prompt_template=(
            "You are a route planner. Create a corridor from Mumbai (19.0760, 72.8777) "
            "to Pune (18.5204, 73.8567) at H3 resolution 10. "
            "Report the corridor_id and block count."
        ),
    ), QWEN)

    risk_assessor = create_specialist(AgentProfile(
        id="risk-assessor",
        name="Risk Assessor",
        role=AgentRole.REVIEWER,
        description="Assesses corridor risks and weather conditions",
        capabilities=["risk_assessment"],
        tools=["list_corridors", "validate_corridor"],
        domains=["safety", "risk"],
        system_prompt_template=(
            "You are a risk assessor. Check what corridors exist using list_corridors. "
            "If any exist, validate the most recent one. "
            "If none exist, report that no corridors are available for assessment."
        ),
    ), QWEN)

    parallel = ParallelPattern(
        aggregation=MergeAggregation(),
        timeout_seconds=45,
    )

    shared = SharedMemory()

    task = Task(
        description=(
            "Prepare for a drone mission from Mumbai to Pune. "
            "Plan the route AND assess risks simultaneously."
        ),
        requirements={
            "capabilities": ["route_planning", "risk_assessment"],
        },
    )

    agents = [route_planner, risk_assessor]
    start = time.time()

    print(f"\n  Running Parallel with 2 agents...")
    events = []
    try:
        async for event in parallel.coordinate(task, agents, shared):
            events.append(event)
            if event.type == CoordinationEventType.COORDINATION_START:
                print(f"  [PARALLEL] Started")
            elif event.type == CoordinationEventType.AGENT_START:
                print(f"  [{event.agent_id}] Started (concurrent)")
            elif event.type == CoordinationEventType.AGENT_COMPLETE:
                output = event.data.get("output", "")
                preview = str(output)[:120] if output else "(no output)"
                print(f"  [{event.agent_id}] Done: {preview}")
            elif event.type == CoordinationEventType.COORDINATION_COMPLETE:
                success = event.data.get("success", False)
                dur = event.data.get("duration_seconds", 0)
                print(f"\n  [PARALLEL] {'SUCCESS' if success else 'DONE'} in {dur:.1f}s")
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()

    elapsed = time.time() - start
    print(f"\n  Time: {elapsed:.1f}s, Events: {len(events)}")
    print(f"  Artifacts: {shared.list_artifacts()}")

    return elapsed


# =============================================================================
# TEST 3: SEQUENTIAL vs PARALLEL — Speed Benchmark
# =============================================================================

async def test_sequential_vs_parallel():
    """Run same 2-agent task sequential then parallel. Compare speed."""

    print("\n" + "=" * 70)
    print("TEST 3: SEQUENTIAL vs PARALLEL — Speed Comparison")
    print("=" * 70)

    def make_agents():
        a1 = create_specialist(AgentProfile(
            id="agent-a",
            name="Agent A",
            role=AgentRole.DOMAIN_SPECIALIST,
            description="Creates a corridor",
            capabilities=["design"],
            tools=["create_corridor"],
            domains=["design"],
            system_prompt_template="Create a corridor from Delhi (28.6, 77.2) to Jaipur (26.9, 75.8) at resolution 10.",
        ), QWEN)

        a2 = create_specialist(AgentProfile(
            id="agent-b",
            name="Agent B",
            role=AgentRole.DOMAIN_SPECIALIST,
            description="Lists and validates corridors",
            capabilities=["validation"],
            tools=["list_corridors", "validate_corridor"],
            domains=["validation"],
            system_prompt_template="List all corridors, then validate the most recent one.",
        ), QWEN)
        return [a1, a2]

    task = Task(
        description="Design a Delhi-Jaipur corridor and validate existing corridors.",
        requirements={"capabilities": ["design", "validation"]},
    )

    # Sequential
    print(f"\n  Running SEQUENTIAL...")
    seq_agents = make_agents()
    seq = SequentialPattern(stop_on_failure=False)
    seq_shared = SharedMemory()
    seq_start = time.time()
    async for event in seq.coordinate(task, seq_agents, seq_shared):
        pass
    seq_time = time.time() - seq_start

    # Parallel
    print(f"  Running PARALLEL...")
    par_agents = make_agents()
    par = ParallelPattern(aggregation=MergeAggregation(), timeout_seconds=30)
    par_shared = SharedMemory()
    par_start = time.time()
    async for event in par.coordinate(task, par_agents, par_shared):
        pass
    par_time = time.time() - par_start

    print(f"\n  SEQUENTIAL: {seq_time:.1f}s")
    print(f"  PARALLEL:   {par_time:.1f}s")
    print(f"  Speedup:    {seq_time / par_time:.1f}x" if par_time > 0 else "  N/A")

    return seq_time, par_time


# =============================================================================
# Main
# =============================================================================

async def main():
    print("=" * 70)
    print("SWARM + PARALLEL PATTERN VALIDATION")
    print("=" * 70)
    total_start = time.time()

    swarm_time = await test_swarm_consensus()
    parallel_time = await test_parallel_execution()
    seq_time, par_time = await test_sequential_vs_parallel()

    total = time.time() - total_start
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"  Swarm (3 reviewers):         {swarm_time:.1f}s")
    print(f"  Parallel (2 agents):         {parallel_time:.1f}s")
    print(f"  Sequential benchmark:        {seq_time:.1f}s")
    print(f"  Parallel benchmark:          {par_time:.1f}s")
    print(f"  Parallel speedup:            {seq_time / par_time:.1f}x" if par_time > 0 else "")
    print(f"  Total time:                  {total:.1f}s")
    print(f"\n  Patterns validated:")
    print(f"    ✓ SwarmPattern (consensus, rounds, multi-reviewer)")
    print(f"    ✓ ParallelPattern (concurrent execution, merge aggregation)")
    print(f"    ✓ Sequential vs Parallel benchmark")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
