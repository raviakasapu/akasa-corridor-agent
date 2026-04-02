"""Drone flight simulation engine.

Simulates a drone flying along a digital rail (ordered sequence of H3 geocode blocks)
with physics (velocity, wind, GPS noise). Implements the core patent concept:
satellite position → geocode block resolution → block membership check → correction.

No real hardware — all positions are computed mathematically.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import h3; fall back to mock if not available
try:
    import h3
    H3_AVAILABLE = True
except ImportError:
    H3_AVAILABLE = False
    logger.warning("h3 library not installed. Using mock geocode functions. Install with: pip install h3")


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class Position:
    """3D geographic position."""
    lat: float
    lon: float
    alt: float = 100.0  # meters above ground

    def to_dict(self) -> Dict[str, float]:
        return {"lat": round(self.lat, 8), "lon": round(self.lon, 8), "alt": round(self.alt, 2)}

    def distance_to(self, other: "Position") -> float:
        """Haversine distance in meters."""
        R = 6371000  # Earth radius in meters
        dlat = math.radians(other.lat - self.lat)
        dlon = math.radians(other.lon - self.lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(self.lat)) * math.cos(math.radians(other.lat)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class Vector3:
    """3D vector for wind, velocity, corrections."""
    dlat: float = 0.0  # degrees per second
    dlon: float = 0.0
    dalt: float = 0.0

    def magnitude(self) -> float:
        return math.sqrt(self.dlat ** 2 + self.dlon ** 2 + self.dalt ** 2)


@dataclass
class BlockTransitionEvent:
    """Event: drone transitioned from one block to another."""
    event_type: str  # BLOCK_TRANSITION, DEVIATION, CORRECTION, FLIGHT_START, FLIGHT_END
    timestamp: str
    block_index: int
    departing_block: Optional[str]
    arriving_block: Optional[str]
    position: Dict[str, float]
    deviation_meters: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Geocode Functions (H3 or Mock)
# =============================================================================

def latlng_to_cell(lat: float, lon: float, resolution: int = 10) -> str:
    """Convert lat/lng to H3 cell ID."""
    if H3_AVAILABLE:
        return h3.latlng_to_cell(lat, lon, resolution)
    # Mock: create a deterministic fake cell ID
    lat_grid = int(lat * 1000) // 7
    lon_grid = int(lon * 1000) // 7
    return f"mock_{resolution}_{lat_grid}_{lon_grid}"


def cell_to_latlng(cell_id: str) -> Tuple[float, float]:
    """Get center lat/lng of an H3 cell."""
    if H3_AVAILABLE:
        return h3.cell_to_latlng(cell_id)
    # Mock: parse from cell ID
    if cell_id.startswith("mock_"):
        parts = cell_id.split("_")
        return float(parts[2]) * 7 / 1000, float(parts[3]) * 7 / 1000
    return 0.0, 0.0


def create_digital_rail(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    resolution: int = 10,
    num_points: int = 50,
) -> List[str]:
    """Create an ordered sequence of H3 cells between two points (the digital rail).

    Interpolates intermediate points along a great circle path and converts
    each to an H3 cell. Removes consecutive duplicates.
    """
    cells = []
    for i in range(num_points + 1):
        t = i / num_points
        lat = start_lat + t * (end_lat - start_lat)
        lon = start_lon + t * (end_lon - start_lon)
        cell = latlng_to_cell(lat, lon, resolution)
        if not cells or cells[-1] != cell:
            cells.append(cell)
    return cells


def cell_edge_length_m(resolution: int = 10) -> float:
    """Approximate edge length of an H3 cell in meters."""
    if H3_AVAILABLE:
        try:
            return h3.average_hexagon_edge_length(resolution, unit="m")
        except Exception:
            pass
    # Approximate values
    edge_lengths = {7: 1220, 8: 461, 9: 174, 10: 65, 11: 25, 12: 9.4}
    return edge_lengths.get(resolution, 65.0)


# =============================================================================
# Flight Ledger (Crypto-Chained)
# =============================================================================

class FlightLedger:
    """Append-only event store with SHA-256 hash chaining.

    Every event is recorded with a cryptographic hash that incorporates
    the previous hash, forming a verifiable chain. This is the core
    compliance mechanism from the patent.
    """

    def __init__(self, flight_id: str):
        self.flight_id = flight_id
        self.events: List[Dict[str, Any]] = []
        self.chain: List[Dict[str, str]] = []
        self._previous_hash = "0" * 64  # Genesis hash

    def record_event(self, event: BlockTransitionEvent) -> str:
        """Record an event and extend the hash chain. Returns block hash."""
        event_dict = {
            "flight_id": self.flight_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "block_index": event.block_index,
            "departing_block": event.departing_block,
            "arriving_block": event.arriving_block,
            "position": event.position,
            "deviation_meters": event.deviation_meters,
            "metadata": event.metadata,
            "index": len(self.events),
        }
        self.events.append(event_dict)

        # Hash chain: SHA256(previous_hash + event_json)
        block_content = self._previous_hash + json.dumps(event_dict, sort_keys=True)
        block_hash = hashlib.sha256(block_content.encode()).hexdigest()
        self.chain.append({"hash": block_hash, "previous": self._previous_hash})
        self._previous_hash = block_hash

        return block_hash

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify the hash chain has not been tampered with."""
        prev = "0" * 64
        for i, event in enumerate(self.events):
            content = prev + json.dumps(event, sort_keys=True)
            expected = hashlib.sha256(content.encode()).hexdigest()
            if expected != self.chain[i]["hash"]:
                return {
                    "valid": False,
                    "failed_at_index": i,
                    "blocks_verified": i,
                    "total_blocks": len(self.events),
                }
            prev = expected

        return {
            "valid": True,
            "blocks_verified": len(self.events),
            "total_blocks": len(self.events),
        }

    def get_conformance_score(self) -> Dict[str, Any]:
        """Calculate corridor conformance score."""
        if not self.events:
            return {"score": 0.0, "total_events": 0}

        total = len(self.events)
        deviations = sum(1 for e in self.events if e["event_type"] == "DEVIATION")
        transitions = sum(1 for e in self.events if e["event_type"] == "BLOCK_TRANSITION")
        corrections = sum(1 for e in self.events if e["event_type"] == "CORRECTION")

        # Conformance = 1 - (deviation_events / total_events)
        score = 1.0 - (deviations / total) if total > 0 else 0.0

        return {
            "score": round(score, 4),
            "total_events": total,
            "transitions": transitions,
            "deviations": deviations,
            "corrections": corrections,
        }

    def generate_certificate(self, corridor_id: str, vehicle_id: str = "DRN-SIM-001") -> Dict[str, Any]:
        """Generate a Corridor Compliance Certificate."""
        conformance = self.get_conformance_score()
        integrity = self.verify_integrity()

        # Find time range
        timestamps = [e["timestamp"] for e in self.events]
        start_time = timestamps[0] if timestamps else None
        end_time = timestamps[-1] if timestamps else None

        # Max deviation
        max_dev = max(
            (e["deviation_meters"] for e in self.events if e.get("deviation_meters", 0) > 0),
            default=0.0,
        )

        return {
            "certificate_id": f"CERT-{uuid.uuid4().hex[:8].upper()}",
            "flight_id": self.flight_id,
            "corridor_id": corridor_id,
            "vehicle_id": vehicle_id,
            "geocode_system": "H3" if H3_AVAILABLE else "Mock-H3",
            "satellite_system": "Simulated-GPS",
            "flight_start_utc": start_time,
            "flight_end_utc": end_time,
            "total_blocks_in_rail": max(
                (e["block_index"] for e in self.events), default=0
            ) + 1,
            "total_transition_events": conformance["transitions"],
            "total_deviation_events": conformance["deviations"],
            "total_correction_events": conformance["corrections"],
            "max_deviation_meters": round(max_dev, 2),
            "corridor_conformance_score": conformance["score"],
            "event_chain_length": len(self.chain),
            "event_chain_final_hash": self.chain[-1]["hash"] if self.chain else None,
            "chain_integrity_verified": integrity["valid"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# Drone Simulator
# =============================================================================

class DroneSimulator:
    """Simulates a drone flying along a digital rail with physics.

    The simulator advances the drone's position each step, applying:
    - Base velocity toward next waypoint
    - Wind displacement
    - GPS noise on position readings
    - Block membership checking (the core patent control loop)
    """

    def __init__(
        self,
        corridor_id: str,
        digital_rail: List[str],
        speed_mps: float = 15.0,
        resolution: int = 10,
    ):
        self.corridor_id = corridor_id
        self.flight_id = f"FLT-{uuid.uuid4().hex[:8].upper()}"
        self.rail = digital_rail
        self.resolution = resolution
        self.speed = speed_mps

        # Position: start at center of first block
        start_lat, start_lon = cell_to_latlng(digital_rail[0])
        self.position = Position(lat=start_lat, lon=start_lon, alt=100.0)
        self.true_position = Position(lat=start_lat, lon=start_lon, alt=100.0)

        # Navigation state
        self.current_block_index = 0
        self.assigned_block = digital_rail[0]
        self.is_active = False
        self.is_complete = False
        self.step_count = 0

        # Physics
        self.wind = Vector3()
        self.gps_noise_magnitude = 0.0

        # Ledger
        self.ledger = FlightLedger(self.flight_id)

        # Timing
        self.start_time: Optional[float] = None
        self.last_step_time: Optional[float] = None

    def start(self) -> Dict[str, Any]:
        """Start the simulation."""
        self.is_active = True
        self.start_time = time.time()
        self.last_step_time = self.start_time

        event = BlockTransitionEvent(
            event_type="FLIGHT_START",
            timestamp=datetime.now(timezone.utc).isoformat(),
            block_index=0,
            departing_block=None,
            arriving_block=self.rail[0],
            position=self.position.to_dict(),
        )
        self.ledger.record_event(event)

        return {
            "flight_id": self.flight_id,
            "corridor_id": self.corridor_id,
            "status": "ACTIVE",
            "start_position": self.position.to_dict(),
            "assigned_block": self.assigned_block,
            "total_blocks": len(self.rail),
        }

    def step(self, dt: float = 0.5) -> Dict[str, Any]:
        """Advance simulation by dt seconds. Returns current state."""
        if not self.is_active or self.is_complete:
            return {"status": "INACTIVE", "message": "Simulation not active"}

        self.step_count += 1

        # Target: center of next block (or current if at last)
        target_idx = min(self.current_block_index + 1, len(self.rail) - 1)
        target_lat, target_lon = cell_to_latlng(self.rail[target_idx])

        # Move toward target
        dlat = (target_lat - self.true_position.lat)
        dlon = (target_lon - self.true_position.lon)
        dist = math.sqrt(dlat ** 2 + dlon ** 2)

        if dist > 1e-8:
            # Normalize and scale by speed (approximate: 1 degree ≈ 111km)
            scale = (self.speed * dt) / (dist * 111000)
            scale = min(scale, 1.0)  # Don't overshoot
            self.true_position.lat += dlat * scale
            self.true_position.lon += dlon * scale

        # Apply wind
        self.true_position.lat += self.wind.dlat * dt
        self.true_position.lon += self.wind.dlon * dt
        self.true_position.alt += self.wind.dalt * dt

        # GPS reading (true position + noise)
        noise_lat = random.gauss(0, self.gps_noise_magnitude * 0.00001) if self.gps_noise_magnitude > 0 else 0
        noise_lon = random.gauss(0, self.gps_noise_magnitude * 0.00001) if self.gps_noise_magnitude > 0 else 0
        self.position = Position(
            lat=self.true_position.lat + noise_lat,
            lon=self.true_position.lon + noise_lon,
            alt=self.true_position.alt,
        )

        # Core patent check: resolve position to geocode block
        current_cell = latlng_to_cell(self.position.lat, self.position.lon, self.resolution)
        is_match = current_cell == self.assigned_block

        # Calculate deviation
        assigned_center = cell_to_latlng(self.assigned_block)
        deviation = self.position.distance_to(
            Position(lat=assigned_center[0], lon=assigned_center[1])
        )

        # Block transition or deviation event
        if is_match:
            # Check if we should advance to next block
            if self.current_block_index < len(self.rail) - 1:
                next_center = cell_to_latlng(self.rail[self.current_block_index + 1])
                dist_to_next = self.position.distance_to(
                    Position(lat=next_center[0], lon=next_center[1])
                )
                edge_len = cell_edge_length_m(self.resolution)
                if dist_to_next < edge_len * 0.8:
                    # Advance
                    old_block = self.assigned_block
                    self.current_block_index += 1
                    self.assigned_block = self.rail[self.current_block_index]

                    event = BlockTransitionEvent(
                        event_type="BLOCK_TRANSITION",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        block_index=self.current_block_index,
                        departing_block=old_block,
                        arriving_block=self.assigned_block,
                        position=self.position.to_dict(),
                    )
                    self.ledger.record_event(event)

                    # Check if flight complete
                    if self.current_block_index >= len(self.rail) - 1:
                        self._complete_flight()
        else:
            # Deviation!
            event = BlockTransitionEvent(
                event_type="DEVIATION",
                timestamp=datetime.now(timezone.utc).isoformat(),
                block_index=self.current_block_index,
                departing_block=self.assigned_block,
                arriving_block=current_cell,
                position=self.position.to_dict(),
                deviation_meters=deviation,
            )
            self.ledger.record_event(event)

        return {
            "step": self.step_count,
            "position": self.position.to_dict(),
            "current_cell": current_cell,
            "assigned_block": self.assigned_block,
            "block_index": self.current_block_index,
            "total_blocks": len(self.rail),
            "is_match": is_match,
            "deviation_meters": round(deviation, 2),
            "status": "COMPLETE" if self.is_complete else "NOMINAL" if is_match else "DEVIATING",
            "wind": {"dlat": self.wind.dlat, "dlon": self.wind.dlon},
            "gps_noise": self.gps_noise_magnitude,
        }

    def apply_correction(self, target_block: str) -> Dict[str, Any]:
        """Apply correction to steer drone back toward assigned block."""
        target_lat, target_lon = cell_to_latlng(target_block)

        # Simple correction: nudge true position toward target
        correction_strength = 0.3  # 30% correction per step
        self.true_position.lat += (target_lat - self.true_position.lat) * correction_strength
        self.true_position.lon += (target_lon - self.true_position.lon) * correction_strength

        event = BlockTransitionEvent(
            event_type="CORRECTION",
            timestamp=datetime.now(timezone.utc).isoformat(),
            block_index=self.current_block_index,
            departing_block=None,
            arriving_block=target_block,
            position=self.true_position.to_dict(),
            metadata={"correction_strength": correction_strength},
        )
        self.ledger.record_event(event)

        return {
            "corrected_position": self.true_position.to_dict(),
            "target_block": target_block,
            "correction_applied": True,
        }

    def inject_wind(self, direction_deg: float, speed_mps: float) -> Dict[str, Any]:
        """Inject wind gust (direction in degrees, speed in m/s)."""
        # Convert to lat/lon displacement rate (very approximate)
        rad = math.radians(direction_deg)
        self.wind = Vector3(
            dlat=math.cos(rad) * speed_mps * 0.000009,  # ~1m in degrees
            dlon=math.sin(rad) * speed_mps * 0.000009,
            dalt=0.0,
        )
        return {
            "wind_direction_deg": direction_deg,
            "wind_speed_mps": speed_mps,
            "wind_vector": {"dlat": self.wind.dlat, "dlon": self.wind.dlon},
            "message": f"Wind gust injected: {speed_mps} m/s from {direction_deg}°",
        }

    def inject_gps_noise(self, magnitude: float) -> Dict[str, Any]:
        """Inject GPS noise (magnitude in meters)."""
        self.gps_noise_magnitude = magnitude
        return {
            "gps_noise_meters": magnitude,
            "message": f"GPS noise set to {magnitude}m",
        }

    def _complete_flight(self) -> None:
        """Mark flight as complete."""
        self.is_complete = True
        self.is_active = False

        event = BlockTransitionEvent(
            event_type="FLIGHT_END",
            timestamp=datetime.now(timezone.utc).isoformat(),
            block_index=self.current_block_index,
            departing_block=self.assigned_block,
            arriving_block=None,
            position=self.position.to_dict(),
        )
        self.ledger.record_event(event)

    def emergency_land(self) -> Dict[str, Any]:
        """Trigger emergency landing."""
        self.is_active = False

        event = BlockTransitionEvent(
            event_type="EMERGENCY_LAND",
            timestamp=datetime.now(timezone.utc).isoformat(),
            block_index=self.current_block_index,
            departing_block=self.assigned_block,
            arriving_block=None,
            position=self.position.to_dict(),
            metadata={"reason": "Emergency landing triggered"},
        )
        self.ledger.record_event(event)

        return {
            "status": "EMERGENCY_LANDED",
            "position": self.position.to_dict(),
            "block_index": self.current_block_index,
            "flight_id": self.flight_id,
        }

    def get_telemetry(self) -> Dict[str, Any]:
        """Get full telemetry snapshot."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        conformance = self.ledger.get_conformance_score()

        return {
            "flight_id": self.flight_id,
            "corridor_id": self.corridor_id,
            "position": self.position.to_dict(),
            "assigned_block": self.assigned_block,
            "block_index": self.current_block_index,
            "total_blocks": len(self.rail),
            "progress_percent": round((self.current_block_index / max(len(self.rail) - 1, 1)) * 100, 1),
            "status": "COMPLETE" if self.is_complete else "ACTIVE" if self.is_active else "INACTIVE",
            "step_count": self.step_count,
            "elapsed_seconds": round(elapsed, 1),
            "wind": {"dlat": self.wind.dlat, "dlon": self.wind.dlon},
            "gps_noise": self.gps_noise_magnitude,
            "conformance_score": conformance["score"],
            "total_events": conformance["total_events"],
            "deviations": conformance["deviations"],
        }


# =============================================================================
# Global Simulation State (per mission)
# =============================================================================

_active_simulations: Dict[str, DroneSimulator] = {}
_corridors: Dict[str, Dict[str, Any]] = {}


def get_simulation(flight_id: Optional[str] = None) -> Optional[DroneSimulator]:
    """Get active simulation by flight_id, or the most recent one."""
    if flight_id:
        return _active_simulations.get(flight_id)
    if _active_simulations:
        return list(_active_simulations.values())[-1]
    return None


def get_corridor(corridor_id: str) -> Optional[Dict[str, Any]]:
    """Get corridor by ID."""
    return _corridors.get(corridor_id)


def list_corridors() -> List[Dict[str, Any]]:
    """List all corridors."""
    return [
        {"corridor_id": cid, "blocks": len(c["rail"]), **{k: v for k, v in c.items() if k != "rail"}}
        for cid, c in _corridors.items()
    ]
