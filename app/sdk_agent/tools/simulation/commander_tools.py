"""AI Mission Commander tools — strategic decision-making layer.

These tools are for the LLM agent (Layer 3). The LLM does NOT do routine
monitoring — the Edge Computer (Layer 2) handles that and pushes alerts.
These tools let the LLM read aggregated status and make strategic decisions.
"""

from typing import Any, Dict
from ..registry import tool
from .engine import get_simulation, get_edge_computer


@tool(
    name="get_edge_status",
    description="Get the Edge Computer's current status and aggregated telemetry. This is your primary situational awareness tool — it shows deviation averages, conformance score, weather conditions, and pending alerts. Call this when you need to understand the current state of the flight.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def get_edge_status() -> Dict[str, Any]:
    edge = get_edge_computer()
    if not edge:
        return {"error": "No active edge computer. Start a simulation first."}
    summary = edge.get_telemetry_summary()
    status = edge.get_status()
    return {
        "edge_status": status,
        "telemetry": summary.to_dict(),
    }


@tool(
    name="get_pending_alerts",
    description="Get all unacknowledged alerts from the Edge Computer. These are situations that need your strategic decision. Review each alert, decide on action, and acknowledge it.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def get_pending_alerts() -> Dict[str, Any]:
    edge = get_edge_computer()
    if not edge:
        return {"error": "No active edge computer."}
    pending = edge.get_pending_alerts()
    return {
        "pending_count": len(pending),
        "alerts": [a.to_dict() for a in pending],
    }


@tool(
    name="acknowledge_alert",
    description="Acknowledge an edge alert and record your decision. This tells the Edge Computer you've handled the situation. Include what action you took (e.g., 'increased correction to 0.6', 'monitoring — within acceptable limits', 'initiated emergency landing').",
    parameters={
        "type": "object",
        "properties": {
            "alert_id": {"type": "string", "description": "The alert ID to acknowledge"},
            "resolution": {"type": "string", "description": "What action you took or decided"},
        },
        "required": ["alert_id", "resolution"],
    },
)
def acknowledge_alert(alert_id: str, resolution: str) -> Dict[str, Any]:
    edge = get_edge_computer()
    if not edge:
        return {"error": "No active edge computer."}
    success = edge.acknowledge_alert(alert_id, resolution)
    if success:
        return {"acknowledged": True, "alert_id": alert_id, "resolution": resolution}
    return {"error": f"Alert '{alert_id}' not found."}


@tool(
    name="set_edge_thresholds",
    description="Adjust the Edge Computer's monitoring thresholds. Use this to make the edge more or less sensitive based on conditions. For example, increase deviation_warn_m in high-wind areas, or lower conformance_warn for critical flights.",
    parameters={
        "type": "object",
        "properties": {
            "deviation_warn_m": {"type": "number", "description": "Deviation warning threshold in meters (default 40)"},
            "deviation_critical_m": {"type": "number", "description": "Deviation critical threshold in meters (default 100)"},
            "wind_warn_mps": {"type": "number", "description": "Wind warning threshold in m/s (default 6)"},
            "conformance_warn": {"type": "number", "description": "Conformance score warning threshold (default 0.85)"},
        },
        "required": [],
    },
)
def set_edge_thresholds(
    deviation_warn_m: float = None,
    deviation_critical_m: float = None,
    wind_warn_mps: float = None,
    conformance_warn: float = None,
) -> Dict[str, Any]:
    edge = get_edge_computer()
    if not edge:
        return {"error": "No active edge computer."}
    kwargs = {}
    if deviation_warn_m is not None:
        kwargs["deviation_warn_m"] = deviation_warn_m
    if deviation_critical_m is not None:
        kwargs["deviation_critical_m"] = deviation_critical_m
    if wind_warn_mps is not None:
        kwargs["wind_warn_mps"] = wind_warn_mps
    if conformance_warn is not None:
        kwargs["conformance_warn"] = conformance_warn
    return edge.set_thresholds(**kwargs)
