"""Mission templates — predefined task sequences for corridor operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Task:
    """A single task in a mission template."""
    id: str
    name: str
    prompt: str
    agent_mode: str = "single"  # which agent mode to use


@dataclass
class Template:
    """A mission template with ordered tasks."""
    id: str
    name: str
    description: str
    tasks: List[Task] = field(default_factory=list)


# Predefined mission templates
TEMPLATES: Dict[str, Template] = {
    "full_mission": Template(
        id="full_mission",
        name="Full Corridor Mission",
        description="Design corridor, fly drone, certify compliance",
        tasks=[
            Task(
                id="design",
                name="Corridor Design",
                prompt=(
                    "Create a new aerial corridor named 'Demo Corridor' between "
                    "San Francisco (37.7749, -122.4194) and Oakland (37.8044, -122.2712) "
                    "at H3 resolution 10. Then validate the corridor."
                ),
                agent_mode="designer",
            ),
            Task(
                id="monitor",
                name="Flight Monitoring",
                prompt=(
                    "Start a simulation on the corridor that was just created. "
                    "Monitor the flight for 8 cycles: check block membership and step "
                    "simulation each cycle. Apply corrections if deviations are detected. "
                    "After monitoring, complete the flight."
                ),
                agent_mode="guardian",
            ),
            Task(
                id="certify",
                name="Compliance Certification",
                prompt=(
                    "Verify the chain integrity of the completed flight. "
                    "Calculate the conformance score. Generate a compliance certificate."
                ),
                agent_mode="compliance",
            ),
        ],
    ),

    "corridor_only": Template(
        id="corridor_only",
        name="Corridor Design Only",
        description="Create and validate a corridor without flying",
        tasks=[
            Task(
                id="design",
                name="Corridor Design",
                prompt=(
                    "Create a new aerial corridor between the specified points. "
                    "Validate the corridor for safety."
                ),
                agent_mode="designer",
            ),
        ],
    ),

    "compliance_audit": Template(
        id="compliance_audit",
        name="Compliance Audit",
        description="Audit an existing flight for compliance",
        tasks=[
            Task(
                id="audit",
                name="Flight Audit",
                prompt=(
                    "Get all flight events. Verify chain integrity. "
                    "Calculate conformance score. Generate compliance certificate. "
                    "Report any anomalies found."
                ),
                agent_mode="compliance",
            ),
        ],
    ),
}


def get_template(template_id: str) -> Optional[Template]:
    """Get a template by ID."""
    return TEMPLATES.get(template_id)


def list_templates() -> List[Dict[str, str]]:
    """List all available templates."""
    return [
        {"id": t.id, "name": t.name, "description": t.description, "tasks": len(t.tasks)}
        for t in TEMPLATES.values()
    ]
