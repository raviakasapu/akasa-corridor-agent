"""Compliance ledger tools — crypto-chained flight records and certificates."""

from typing import Any, Dict
from ..registry import tool
from ..simulation.engine import get_simulation


@tool(
    name="get_flight_events",
    description="Get all block-transition and deviation events from the flight ledger.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional, uses latest)"},
            "limit": {"type": "integer", "description": "Max events to return (default 50)"},
        },
        "required": [],
    },
)
def get_flight_events(flight_id: str = "", limit: int = 50) -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No flight found."}

    events = sim.ledger.events[-limit:]
    return {
        "flight_id": sim.flight_id,
        "total_events": len(sim.ledger.events),
        "returned_events": len(events),
        "events": events,
    }


@tool(
    name="verify_chain_integrity",
    description="Verify the cryptographic hash chain of the flight ledger has not been tampered with.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def verify_chain_integrity(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No flight found."}

    result = sim.ledger.verify_integrity()
    result["flight_id"] = sim.flight_id
    return result


@tool(
    name="calculate_conformance_score",
    description="Calculate the corridor conformance score for a flight. Score of 1.0 means perfect compliance.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def calculate_conformance_score(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No flight found."}

    result = sim.ledger.get_conformance_score()
    result["flight_id"] = sim.flight_id
    return result


@tool(
    name="generate_certificate",
    description="Generate a Corridor Compliance Certificate for a completed flight. Includes conformance score, hash chain, and integrity verification.",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID (optional)"},
        },
        "required": [],
    },
)
def generate_certificate(flight_id: str = "") -> Dict[str, Any]:
    sim = get_simulation(flight_id if flight_id else None)
    if not sim:
        return {"error": "No flight found."}

    cert = sim.ledger.generate_certificate(
        corridor_id=sim.corridor_id,
        vehicle_id="DRN-SIM-001",
    )
    return cert
