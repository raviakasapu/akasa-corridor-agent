"""Drone simulation tools — exposed to agents via @tool decorator."""

from typing import Any, Dict
from ..registry import tool
from .engine import (
    DroneSimulator, create_digital_rail, get_simulation, get_corridor,
    list_corridors as _list_corridors, _active_simulations, _corridors,
    latlng_to_cell, cell_to_latlng,
)


@tool(
    name="start_simulation",
    description="Start a drone flight simulation on a corridor. The drone will begin at the first block of the digital rail.",
    parameters={
        "type": "object",
        "properties": {
            "corridor_id": {"type": "string", "description": "Corridor ID to fly"},
            "speed_mps": {"type": "number", "description": "Drone speed in m/s (default 15)"},
        },
        "required": ["corridor_id"],
    },
)
def start_simulation(corridor_id: str, speed_mps: float = 15.0) -> Dict[str, Any]:
    corridor = get_corridor(corridor_id)
    if not corridor:
        return {"error": f"Corridor '{corridor_id}' not found. Use create_corridor first."}

    sim = DroneSimulator(
        corridor_id=corridor_id,
        digital_rail=corridor["rail"],
        speed_mps=speed_mps,
        resolution=corridor.get("resolution", 10),
    )
    result = sim.start()
    _active_simulations[sim.flight_id] = sim
    return result


@tool(
    name="step_simulation",
    description="Advance the drone simulation by one time step (0.5s). Returns position, block membership, and deviation status.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional, uses latest if omitted)"},
            "steps": {"type": "integer", "description": "Number of steps to advance (default 1, max 20)"},
        },
        "required": [],
    },
)
def step_simulation(flight_id: str = "", steps: int = 1) -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No active simulation. Use start_simulation first."}

    steps = min(max(steps, 1), 20)
    state = None
    for _ in range(steps):
        state = sim.step(dt=0.5)
        if state.get("status") == "COMPLETE":
            break
    return state


@tool(
    name="get_drone_position",
    description="Get the current simulated drone position (lat, lon, alt) and navigation state.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def get_drone_position(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No active simulation."}

    return {
        "flight_id": sim.flight_id,
        "position": sim.position.to_dict(),
        "assigned_block": sim.assigned_block,
        "block_index": sim.current_block_index,
        "total_blocks": len(sim.rail),
        "is_active": sim.is_active,
        "is_complete": sim.is_complete,
    }


@tool(
    name="check_block_membership",
    description="CORE PATENT CHECK: Resolve drone's satellite position to a geocode block and compare to assigned block. Returns match status and deviation distance.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def check_block_membership(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No active simulation."}

    current_cell = latlng_to_cell(sim.position.lat, sim.position.lon, sim.resolution)
    assigned = sim.assigned_block
    is_match = current_cell == assigned

    assigned_center = cell_to_latlng(assigned)
    from .engine import Position
    deviation = sim.position.distance_to(
        Position(lat=assigned_center[0], lon=assigned_center[1])
    )

    return {
        "flight_id": sim.flight_id,
        "current_block": current_cell,
        "assigned_block": assigned,
        "is_match": is_match,
        "deviation_meters": round(deviation, 2),
        "block_index": sim.current_block_index,
        "total_blocks": len(sim.rail),
        "status": "NOMINAL" if is_match else "DEVIATING",
    }


@tool(
    name="generate_correction",
    description="Generate and apply a correction vector to steer the drone back toward its assigned geocode block.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def generate_correction(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No active simulation."}
    return sim.apply_correction(sim.assigned_block)


@tool(
    name="inject_wind_gust",
    description="Simulate a wind gust disruption. Pushes the drone off course to test deviation handling.",
    parameters={
        "type": "object",
        "properties": {
            "direction_deg": {"type": "number", "description": "Wind direction in degrees (0=North, 90=East)"},
            "speed_mps": {"type": "number", "description": "Wind speed in meters per second"},
        },
        "required": ["direction_deg", "speed_mps"],
    },
)
def inject_wind_gust(direction_deg: float, speed_mps: float) -> Dict[str, Any]:
    sim = get_simulation()
    if not sim:
        return {"error": "No active simulation."}
    return sim.inject_wind(direction_deg, speed_mps)


@tool(
    name="inject_gps_noise",
    description="Simulate GPS signal degradation by adding noise to position readings.",
    parameters={
        "type": "object",
        "properties": {
            "magnitude_meters": {"type": "number", "description": "GPS noise magnitude in meters"},
        },
        "required": ["magnitude_meters"],
    },
)
def inject_gps_noise(magnitude_meters: float) -> Dict[str, Any]:
    sim = get_simulation()
    if not sim:
        return {"error": "No active simulation."}
    return sim.inject_gps_noise(magnitude_meters)


@tool(
    name="get_flight_telemetry",
    description="Get full telemetry snapshot including position, progress, conformance score, and event counts.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def get_flight_telemetry(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No active simulation."}
    return sim.get_telemetry()


@tool(
    name="complete_flight",
    description="End the flight normally. Triggers final compliance recording.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def complete_flight(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No active simulation."}
    sim._complete_flight()
    return {
        "status": "COMPLETED",
        "flight_id": sim.flight_id,
        "final_telemetry": sim.get_telemetry(),
    }


@tool(
    name="emergency_land",
    description="Trigger an emergency landing. Aborts the flight immediately.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def emergency_land(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No active simulation."}
    return sim.emergency_land()
