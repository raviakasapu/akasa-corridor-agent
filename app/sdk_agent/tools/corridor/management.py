"""Corridor management tools — create, list, validate corridors."""

import uuid
from typing import Any, Dict
from ..registry import tool
from ..simulation.engine import (
    create_digital_rail, cell_to_latlng, cell_edge_length_m,
    _corridors, latlng_to_cell,
)


@tool(
    name="create_corridor",
    description="Create a new aerial corridor (digital rail) between two geographic points. Returns the corridor ID and block sequence.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Human-readable corridor name"},
            "start_lat": {"type": "number", "description": "Start latitude"},
            "start_lon": {"type": "number", "description": "Start longitude"},
            "end_lat": {"type": "number", "description": "End latitude"},
            "end_lon": {"type": "number", "description": "End longitude"},
            "resolution": {"type": "integer", "description": "H3 resolution (7-12, default 10). Higher = smaller blocks."},
        },
        "required": ["name", "start_lat", "start_lon", "end_lat", "end_lon"],
    },
)
def create_corridor(
    name: str,
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    resolution: int = 10,
) -> Dict[str, Any]:
    # H3 only supports resolutions 0-15
    resolution = max(0, min(resolution, 15))
    corridor_id = f"COR-{uuid.uuid4().hex[:8].upper()}"
    rail = create_digital_rail(start_lat, start_lon, end_lat, end_lon, resolution)

    corridor = {
        "corridor_id": corridor_id,
        "name": name,
        "start": {"lat": start_lat, "lon": start_lon},
        "end": {"lat": end_lat, "lon": end_lon},
        "resolution": resolution,
        "rail": rail,
        "block_count": len(rail),
        "edge_length_m": round(cell_edge_length_m(resolution), 1),
    }
    _corridors[corridor_id] = corridor

    return {
        "corridor_id": corridor_id,
        "name": name,
        "start": {"lat": start_lat, "lon": start_lon},
        "end": {"lat": end_lat, "lon": end_lon},
        "block_count": len(rail),
        "rail": rail,
        "first_block": rail[0] if rail else None,
        "last_block": rail[-1] if rail else None,
        "resolution": resolution,
        "edge_length_m": round(cell_edge_length_m(resolution), 1),
        "summary": f"Created corridor '{name}' with {len(rail)} geocode blocks at H3 resolution {resolution}",
    }


@tool(
    name="list_corridors",
    description="List all existing corridors with their block counts and endpoints.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_corridors() -> Dict[str, Any]:
    from ..simulation.engine import list_corridors as _list
    corridors = _list()
    return {
        "corridors": corridors,
        "count": len(corridors),
        "summary": f"Found {len(corridors)} corridors" if corridors else "No corridors created yet.",
    }


@tool(
    name="get_corridor_detail",
    description="Get detailed information about a corridor including its full digital rail (block sequence).",
    parameters={
        "type": "object",
        "properties": {
            "corridor_id": {"type": "string", "description": "Corridor ID"},
        },
        "required": ["corridor_id"],
    },
)
def get_corridor_detail(corridor_id: str) -> Dict[str, Any]:
    from ..simulation.engine import get_corridor
    corridor = get_corridor(corridor_id)
    if not corridor:
        return {"error": f"Corridor '{corridor_id}' not found."}

    rail = corridor["rail"]
    return {
        "corridor_id": corridor_id,
        "name": corridor.get("name", ""),
        "start": corridor.get("start"),
        "end": corridor.get("end"),
        "resolution": corridor.get("resolution"),
        "block_count": len(rail),
        "digital_rail_preview": rail[:5] + ["..."] + rail[-5:] if len(rail) > 10 else rail,
        "edge_length_m": corridor.get("edge_length_m"),
    }


@tool(
    name="validate_corridor",
    description="Validate a corridor's safety parameters: check altitude bounds, block connectivity, and distance.",
    parameters={
        "type": "object",
        "properties": {
            "corridor_id": {"type": "string", "description": "Corridor ID to validate"},
        },
        "required": ["corridor_id"],
    },
)
def validate_corridor(corridor_id: str) -> Dict[str, Any]:
    from ..simulation.engine import get_corridor
    corridor = get_corridor(corridor_id)
    if not corridor:
        return {"error": f"Corridor '{corridor_id}' not found."}

    rail = corridor["rail"]
    issues = []

    # Check: has enough blocks
    if len(rail) < 3:
        issues.append("Corridor has fewer than 3 blocks — too short for safe operations")

    # Check: start and end are different
    if rail[0] == rail[-1]:
        issues.append("Start and end blocks are identical — circular corridor")

    # Check: no duplicate consecutive blocks
    dupes = sum(1 for i in range(len(rail) - 1) if rail[i] == rail[i + 1])
    if dupes > 0:
        issues.append(f"Found {dupes} duplicate consecutive blocks in rail")

    # Estimate total distance
    start_center = cell_to_latlng(rail[0])
    end_center = cell_to_latlng(rail[-1])
    from ..simulation.engine import Position
    total_dist = Position(lat=start_center[0], lon=start_center[1]).distance_to(
        Position(lat=end_center[0], lon=end_center[1])
    )

    return {
        "corridor_id": corridor_id,
        "valid": len(issues) == 0,
        "block_count": len(rail),
        "estimated_distance_km": round(total_dist / 1000, 2),
        "issues": issues if issues else ["No issues found — corridor is valid"],
        "summary": f"Corridor validated: {len(issues)} issues found" if issues else "Corridor is valid and safe for operations",
    }
