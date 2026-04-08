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
class EnvironmentState:
    """Current environmental conditions affecting the drone."""
    wind_direction_deg: float = 0.0
    wind_speed_mps: float = 0.0
    wind_gust_timer: float = 3.0
    gps_noise_magnitude: float = 0.0
    gps_noise_timer: float = 5.0
    turbulence_intensity: float = 0.0
    turbulence_timer: float = 2.0


@dataclass
class AutopilotState:
    """Autopilot correction state."""
    correction_strength: float = 0.3
    correction_applied_this_step: bool = False
    correction_vector: Dict[str, float] = field(default_factory=dict)
    cumulative_corrections: int = 0


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

        # Environment & autopilot (realistic simulation)
        self.environment = EnvironmentState()
        self.autopilot = AutopilotState()
        self.environment_enabled = True

        # Realistic simulation constants
        self.WIND_CHANGE_INTERVAL = (3.0, 8.0)
        self.WIND_SPEED_RANGE = (0.0, 4.0)
        self.GPS_NOISE_CHANGE_INTERVAL = (5.0, 15.0)
        self.GPS_NOISE_RANGE = (0.0, 2.5)
        self.TURBULENCE_CHANGE_INTERVAL = (2.0, 6.0)
        self.TURBULENCE_INTENSITY_RANGE = (0.0, 0.3)
        self.DEVIATION_CORRECTION_THRESHOLD_M = 15.0

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

    def _update_environment(self, dt: float) -> None:
        """Randomly update environmental conditions (wind, GPS noise, turbulence)."""
        if not self.environment_enabled:
            return

        env = self.environment

        # Wind gusts: change direction and speed periodically
        env.wind_gust_timer -= dt
        if env.wind_gust_timer <= 0:
            env.wind_direction_deg = random.uniform(0, 360)
            env.wind_speed_mps = random.uniform(*self.WIND_SPEED_RANGE)
            env.wind_gust_timer = random.uniform(*self.WIND_CHANGE_INTERVAL)
            rad = math.radians(env.wind_direction_deg)
            self.wind = Vector3(
                dlat=math.cos(rad) * env.wind_speed_mps * 0.000009,
                dlon=math.sin(rad) * env.wind_speed_mps * 0.000009,
            )

        # GPS noise: fluctuate magnitude
        env.gps_noise_timer -= dt
        if env.gps_noise_timer <= 0:
            env.gps_noise_magnitude = random.uniform(*self.GPS_NOISE_RANGE)
            self.gps_noise_magnitude = env.gps_noise_magnitude
            env.gps_noise_timer = random.uniform(*self.GPS_NOISE_CHANGE_INTERVAL)

        # Turbulence intensity
        env.turbulence_timer -= dt
        if env.turbulence_timer <= 0:
            env.turbulence_intensity = random.uniform(*self.TURBULENCE_INTENSITY_RANGE)
            env.turbulence_timer = random.uniform(*self.TURBULENCE_CHANGE_INTERVAL)

    def _apply_turbulence(self, dt: float) -> None:
        """Apply random position jitter from turbulence."""
        intensity = self.environment.turbulence_intensity
        if intensity > 0:
            self.true_position.lat += random.gauss(0, intensity * 0.000005 * dt)
            self.true_position.lon += random.gauss(0, intensity * 0.000005 * dt)
            self.true_position.alt += random.gauss(0, intensity * 0.5 * dt)
            # Clamp altitude
            self.true_position.alt = max(50.0, min(200.0, self.true_position.alt))

    def _apply_autopilot_correction(self, is_match: bool, deviation_m: float) -> None:
        """Autopilot self-correction: only when drone has LEFT its assigned block.

        Corrects laterally toward the assigned block center, but does NOT
        fight forward movement along the rail. This mimics a real autopilot
        that maintains the flight path corridor without slowing progress.
        """
        self.autopilot.correction_applied_this_step = False
        self.autopilot.correction_vector = {}

        # Only correct when the drone has actually left its assigned H3 cell
        if is_match:
            return

        # Only correct if deviation is significant
        if deviation_m <= self.DEVIATION_CORRECTION_THRESHOLD_M:
            return

        # Compute correction toward assigned block center
        target_lat, target_lon = cell_to_latlng(self.assigned_block)
        dlat = target_lat - self.true_position.lat
        dlon = target_lon - self.true_position.lon

        # Project out the forward component: only correct the lateral drift
        # Forward direction is toward next block
        next_idx = min(self.current_block_index + 1, len(self.rail) - 1)
        fwd_lat, fwd_lon = cell_to_latlng(self.rail[next_idx])
        fwd_dlat = fwd_lat - self.true_position.lat
        fwd_dlon = fwd_lon - self.true_position.lon
        fwd_mag = math.sqrt(fwd_dlat ** 2 + fwd_dlon ** 2)

        if fwd_mag > 1e-10:
            # Normalize forward vector
            fwd_dlat /= fwd_mag
            fwd_dlon /= fwd_mag
            # Remove forward component from correction (keep only lateral)
            dot = dlat * fwd_dlat + dlon * fwd_dlon
            dlat -= dot * fwd_dlat
            dlon -= dot * fwd_dlon

        strength = self.autopilot.correction_strength
        corr_lat = dlat * strength
        corr_lon = dlon * strength
        self.true_position.lat += corr_lat
        self.true_position.lon += corr_lon

        self.autopilot.correction_applied_this_step = True
        self.autopilot.correction_vector = {
            "dlat": round(corr_lat, 10),
            "dlon": round(corr_lon, 10),
            "strength": strength,
        }
        self.autopilot.cumulative_corrections += 1

        event = BlockTransitionEvent(
            event_type="CORRECTION",
            timestamp=datetime.now(timezone.utc).isoformat(),
            block_index=self.current_block_index,
            departing_block=None,
            arriving_block=self.assigned_block,
            position=self.true_position.to_dict(),
            deviation_meters=deviation_m,
            metadata={"correction_strength": strength, "auto": True},
        )
        self.ledger.record_event(event)

    def set_correction_strength(self, strength: float) -> Dict[str, Any]:
        """LLM supervisor can override autopilot correction strength (0.0-1.0)."""
        strength = max(0.0, min(1.0, strength))
        self.autopilot.correction_strength = strength
        return {"correction_strength": strength, "message": f"Correction strength set to {strength}"}

    def step(self, dt: float = 0.5) -> Dict[str, Any]:
        """Advance simulation by dt seconds. Returns current state."""
        if not self.is_active or self.is_complete:
            return {"flight_id": self.flight_id, "status": "INACTIVE", "message": "Simulation not active"}

        # Clamp dt to prevent physics jumps
        dt = min(dt, 1.5)
        self.step_count += 1

        # 1. Update environment (random wind, GPS noise, turbulence)
        self._update_environment(dt)

        # 2. Move toward next block center
        target_idx = min(self.current_block_index + 1, len(self.rail) - 1)
        target_lat, target_lon = cell_to_latlng(self.rail[target_idx])

        dlat = (target_lat - self.true_position.lat)
        dlon = (target_lon - self.true_position.lon)
        dist = math.sqrt(dlat ** 2 + dlon ** 2)

        if dist > 1e-8:
            scale = (self.speed * dt) / (dist * 111000)
            scale = min(scale, 1.0)
            self.true_position.lat += dlat * scale
            self.true_position.lon += dlon * scale

        # 3. Apply wind displacement
        self.true_position.lat += self.wind.dlat * dt
        self.true_position.lon += self.wind.dlon * dt
        self.true_position.alt += self.wind.dalt * dt

        # 4. Apply turbulence jitter
        self._apply_turbulence(dt)

        # 5. GPS reading (true position + noise)
        noise_lat = random.gauss(0, self.gps_noise_magnitude * 0.00001) if self.gps_noise_magnitude > 0 else 0
        noise_lon = random.gauss(0, self.gps_noise_magnitude * 0.00001) if self.gps_noise_magnitude > 0 else 0
        self.position = Position(
            lat=self.true_position.lat + noise_lat,
            lon=self.true_position.lon + noise_lon,
            alt=self.true_position.alt,
        )

        # 6. Core patent check: resolve position to geocode block
        current_cell = latlng_to_cell(self.position.lat, self.position.lon, self.resolution)
        is_match = current_cell == self.assigned_block

        assigned_center = cell_to_latlng(self.assigned_block)
        deviation = self.position.distance_to(
            Position(lat=assigned_center[0], lon=assigned_center[1])
        )

        # 7. Block transition: advance when closer to next block than current
        if self.current_block_index < len(self.rail) - 1:
            next_center = cell_to_latlng(self.rail[self.current_block_index + 1])
            dist_to_next = self.position.distance_to(
                Position(lat=next_center[0], lon=next_center[1])
            )
            dist_to_current = deviation
            edge_len = cell_edge_length_m(self.resolution)
            if dist_to_next < dist_to_current or dist_to_next < edge_len:
                old_block = self.assigned_block
                self.current_block_index += 1
                self.assigned_block = self.rail[self.current_block_index]

                current_cell = latlng_to_cell(self.position.lat, self.position.lon, self.resolution)
                is_match = current_cell == self.assigned_block
                assigned_center = cell_to_latlng(self.assigned_block)
                deviation = self.position.distance_to(
                    Position(lat=assigned_center[0], lon=assigned_center[1])
                )

                event = BlockTransitionEvent(
                    event_type="BLOCK_TRANSITION",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    block_index=self.current_block_index,
                    departing_block=old_block,
                    arriving_block=self.assigned_block,
                    position=self.position.to_dict(),
                )
                self.ledger.record_event(event)

                if self.current_block_index >= len(self.rail) - 1:
                    self._complete_flight()

        # 8. Autopilot self-correction (only when drone has left its assigned block)
        self._apply_autopilot_correction(is_match, deviation)

        # 9. Record deviation event (after autopilot, so we see the pre-correction state)
        if not is_match and not self.is_complete:
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

        elapsed = time.time() - self.start_time if self.start_time else 0

        return {
            "flight_id": self.flight_id,
            "step": self.step_count,
            "position": self.position.to_dict(),
            "current_block": current_cell,
            "assigned_block": self.assigned_block,
            "block_index": self.current_block_index,
            "total_blocks": len(self.rail),
            "is_match": is_match,
            "deviation_meters": round(deviation, 2),
            "status": "COMPLETE" if self.is_complete else "NOMINAL" if is_match else "DEVIATING",
            "progress_percent": round((self.current_block_index / max(len(self.rail) - 1, 1)) * 100, 1),
            "elapsed_seconds": round(elapsed, 1),
            "environment": {
                "wind_direction_deg": round(self.environment.wind_direction_deg, 1),
                "wind_speed_mps": round(self.environment.wind_speed_mps, 2),
                "gps_noise_meters": round(self.environment.gps_noise_magnitude, 2),
                "turbulence_intensity": round(self.environment.turbulence_intensity, 3),
            },
            "autopilot": {
                "correction_applied": self.autopilot.correction_applied_this_step,
                "correction_strength": self.autopilot.correction_strength,
                "cumulative_corrections": self.autopilot.cumulative_corrections,
            },
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

# Edge computers per flight
_edge_computers: Dict[str, Any] = {}  # flight_id -> EdgeComputer

# Callbacks for pushing events to clients
_tick_callbacks: Dict[str, Any] = {}  # flight_id -> async callback
_alert_callbacks: Dict[str, Any] = {}  # flight_id -> async callback
_edge_telemetry_callbacks: Dict[str, Any] = {}  # flight_id -> async callback


async def run_simulation_loop(
    sim: DroneSimulator,
    tick_interval: float = 0.3,
) -> None:
    """Run the simulation in a background async loop with 3-layer architecture.

    Layer 1 (Autopilot): DroneSimulator.step() — millisecond physics
    Layer 2 (Edge Computer): Monitors every 5 ticks, generates alerts
    Layer 3 (AI Agent): Receives alerts via WebSocket, makes strategic decisions
    """
    import asyncio
    from .edge_computer import EdgeComputer

    # Create edge computer for this flight
    edge = EdgeComputer(sim, check_interval=5)
    _edge_computers[sim.flight_id] = edge

    last_time = time.monotonic()
    telemetry_counter = 0

    while sim.is_active and not sim.is_complete:
        now = time.monotonic()
        dt = now - last_time
        last_time = now

        # Layer 1: Autopilot step
        state = sim.step(dt=dt)

        # Layer 2: Edge computer processes tick
        new_alerts = edge.process_tick(state)

        # Push tick to frontend
        tick_cb = _tick_callbacks.get(sim.flight_id)
        if tick_cb:
            try:
                await tick_cb(state)
            except Exception:
                pass

        # Push any new alerts
        alert_cb = _alert_callbacks.get(sim.flight_id)
        if alert_cb and new_alerts:
            for alert in new_alerts:
                try:
                    await alert_cb(alert.to_dict())
                except Exception:
                    pass

        # Push edge telemetry summary every ~30 ticks (~9 seconds)
        telemetry_counter += 1
        if telemetry_counter >= 30:
            telemetry_counter = 0
            telem_cb = _edge_telemetry_callbacks.get(sim.flight_id)
            if telem_cb:
                try:
                    await telem_cb(edge.get_telemetry_summary().to_dict())
                except Exception:
                    pass

        await asyncio.sleep(tick_interval)

    # Final tick
    final_state = {
        "flight_id": sim.flight_id,
        "position": sim.position.to_dict(),
        "block_index": sim.current_block_index,
        "total_blocks": len(sim.rail),
        "status": "COMPLETE",
        "deviation_meters": 0,
        "assigned_block": sim.assigned_block,
        "current_block": sim.assigned_block,
        "progress_percent": 100.0,
        "elapsed_seconds": round(time.time() - sim.start_time, 1) if sim.start_time else 0,
        "environment": {
            "wind_direction_deg": 0, "wind_speed_mps": 0,
            "gps_noise_meters": 0, "turbulence_intensity": 0,
        },
        "autopilot": {
            "correction_applied": False,
            "correction_strength": sim.autopilot.correction_strength,
            "cumulative_corrections": sim.autopilot.cumulative_corrections,
        },
    }
    tick_cb = _tick_callbacks.get(sim.flight_id)
    if tick_cb:
        try:
            await tick_cb(final_state)
        except Exception:
            pass


def register_tick_callback(flight_id: str, callback) -> None:
    """Register an async callback for simulation tick events."""
    _tick_callbacks[flight_id] = callback


def register_alert_callback(flight_id: str, callback) -> None:
    """Register an async callback for edge alert events."""
    _alert_callbacks[flight_id] = callback


def register_edge_telemetry_callback(flight_id: str, callback) -> None:
    """Register an async callback for edge telemetry summaries."""
    _edge_telemetry_callbacks[flight_id] = callback


def get_edge_computer(flight_id: str = None):
    """Get edge computer for a flight."""
    if flight_id:
        return _edge_computers.get(flight_id)
    if _edge_computers:
        return list(_edge_computers.values())[-1]
    return None


def unregister_tick_callback(flight_id: str) -> None:
    """Remove all callbacks for a flight."""
    _tick_callbacks.pop(flight_id, None)
    _alert_callbacks.pop(flight_id, None)
    _edge_telemetry_callbacks.pop(flight_id, None)


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
