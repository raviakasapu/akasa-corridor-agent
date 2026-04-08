"""Edge Computer — sub-second monitoring layer between autopilot and AI.

Processes every N simulation ticks. Performs:
- Block membership verification (core patent check)
- Deviation threshold monitoring with auto-escalation
- Geofence enforcement
- Conformance tracking
- Alert generation for the AI Mission Commander

The AI agent does NOT poll — the edge pushes alerts when decisions are needed.
"""

from __future__ import annotations

import uuid
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import DroneSimulator


# =============================================================================
# Alert Types
# =============================================================================

class AlertType:
    DEVIATION_WARNING = "DEVIATION_WARNING"
    DEVIATION_CRITICAL = "DEVIATION_CRITICAL"
    GEOFENCE_APPROACH = "GEOFENCE_APPROACH"
    GEOFENCE_BREACH = "GEOFENCE_BREACH"
    CONFORMANCE_DEGRADING = "CONFORMANCE_DEGRADING"
    STALL_DETECTED = "STALL_DETECTED"
    WEATHER_HAZARD = "WEATHER_HAZARD"
    WEATHER_EXTREME = "WEATHER_EXTREME"
    BLOCK_MISMATCH_PERSISTENT = "BLOCK_MISMATCH_PERSISTENT"
    FLIGHT_MILESTONE = "FLIGHT_MILESTONE"
    FLIGHT_COMPLETE = "FLIGHT_COMPLETE"


ALERT_MESSAGES = {
    AlertType.DEVIATION_WARNING: "Drone deviating from assigned block — monitoring",
    AlertType.DEVIATION_CRITICAL: "Critical deviation — AI intervention recommended",
    AlertType.GEOFENCE_APPROACH: "Drone approaching corridor boundary",
    AlertType.GEOFENCE_BREACH: "GEOFENCE BREACH — drone outside corridor bounds",
    AlertType.CONFORMANCE_DEGRADING: "Flight conformance score degrading",
    AlertType.STALL_DETECTED: "Drone not advancing through blocks",
    AlertType.WEATHER_HAZARD: "Adverse weather conditions detected",
    AlertType.WEATHER_EXTREME: "Extreme weather — consider emergency landing",
    AlertType.BLOCK_MISMATCH_PERSISTENT: "Persistent block mismatch despite corrections",
    AlertType.FLIGHT_MILESTONE: "Flight milestone reached",
    AlertType.FLIGHT_COMPLETE: "Flight has reached the final block",
}


@dataclass
class EdgeAlert:
    alert_id: str
    alert_type: str
    severity: str  # INFO, WARNING, CRITICAL
    timestamp: str
    flight_id: str
    step: int
    position: Dict[str, float]
    data: Dict[str, Any]
    message: str
    acknowledged: bool = False
    resolution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "flight_id": self.flight_id,
            "step": self.step,
            "position": self.position,
            "data": self.data,
            "message": self.message,
            "acknowledged": self.acknowledged,
            "resolution": self.resolution,
        }


@dataclass
class EdgeTelemetrySummary:
    """Aggregated telemetry for AI consumption."""
    flight_id: str
    window_steps: int
    avg_deviation_m: float
    max_deviation_m: float
    block_match_rate: float
    blocks_traversed: int
    current_block_index: int
    total_blocks: int
    corrections_in_window: int
    avg_wind_speed: float
    max_wind_speed: float
    avg_turbulence: float
    conformance_score: float
    progress_percent: float
    active_alerts: int
    pending_alerts: int
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flight_id": self.flight_id,
            "window_steps": self.window_steps,
            "avg_deviation_m": round(self.avg_deviation_m, 1),
            "max_deviation_m": round(self.max_deviation_m, 1),
            "block_match_rate": round(self.block_match_rate, 3),
            "blocks_traversed": self.blocks_traversed,
            "current_block_index": self.current_block_index,
            "total_blocks": self.total_blocks,
            "corrections_in_window": self.corrections_in_window,
            "avg_wind_speed": round(self.avg_wind_speed, 2),
            "max_wind_speed": round(self.max_wind_speed, 2),
            "avg_turbulence": round(self.avg_turbulence, 3),
            "conformance_score": round(self.conformance_score, 3),
            "progress_percent": round(self.progress_percent, 1),
            "active_alerts": self.active_alerts,
            "pending_alerts": self.pending_alerts,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }


# =============================================================================
# Edge Computer
# =============================================================================

class EdgeComputer:
    """Sub-second monitoring layer between autopilot and AI Mission Commander."""

    def __init__(self, sim: "DroneSimulator", check_interval: int = 5):
        self.sim = sim
        self.check_interval = check_interval
        self.alerts: List[EdgeAlert] = []
        self._tick_buffer: List[Dict] = []
        self._last_check_step = 0
        self._checks_performed = 0

        # Thresholds (configurable by AI)
        self.deviation_warn_m = 40.0
        self.deviation_critical_m = 100.0
        self.wind_warn_mps = 6.0
        self.wind_extreme_mps = 10.0
        self.turbulence_warn = 0.25
        self.turbulence_extreme = 0.4
        self.conformance_warn = 0.85
        self.stall_threshold_steps = 30

        # Internal tracking
        self._consecutive_deviations = 0
        self._consecutive_mismatches = 0
        self._stall_counter = 0
        self._last_block_index = 0
        self._milestone_25 = False
        self._milestone_50 = False
        self._milestone_75 = False
        self._recent_alert_types: Dict[str, int] = {}  # type -> step last fired

        # Auto-escalation: emergency land if CRITICAL unacknowledged for N steps
        self.auto_escalation_steps = 100
        self._critical_unack_since: Optional[int] = None

    def process_tick(self, tick_state: Dict) -> List[EdgeAlert]:
        """Process a simulation tick. Returns any new alerts generated."""
        self._tick_buffer.append(tick_state)
        new_alerts = []

        step = tick_state.get("step", 0)
        if step - self._last_check_step >= self.check_interval:
            self._last_check_step = step
            self._checks_performed += 1
            new_alerts = self._run_checks(tick_state)

        # Auto-escalation check
        if self._critical_unack_since is not None:
            steps_since = step - self._critical_unack_since
            if steps_since >= self.auto_escalation_steps and self.sim.is_active:
                self.sim._complete_flight()
                alert = self._create_alert(
                    AlertType.GEOFENCE_BREACH, "CRITICAL", tick_state,
                    {"reason": "Auto-escalation: CRITICAL alert unacknowledged",
                     "steps_unacknowledged": steps_since},
                )
                new_alerts.append(alert)
                self._critical_unack_since = None

        return new_alerts

    def _run_checks(self, state: Dict) -> List[EdgeAlert]:
        """Core edge checks."""
        alerts = []
        step = state.get("step", 0)
        deviation = state.get("deviation_meters", 0)
        is_match = state.get("is_match", True)
        block_index = state.get("block_index", 0)
        progress = state.get("progress_percent", 0)
        env = state.get("environment", {})
        wind_speed = env.get("wind_speed_mps", 0)
        turbulence = env.get("turbulence_intensity", 0)

        # 1. Deviation monitoring
        if deviation > self.deviation_critical_m:
            self._consecutive_deviations += 1
            if self._should_fire(AlertType.DEVIATION_CRITICAL, step, cooldown=20):
                alerts.append(self._create_alert(
                    AlertType.DEVIATION_CRITICAL, "CRITICAL", state,
                    {"deviation_m": round(deviation, 1),
                     "consecutive_checks": self._consecutive_deviations,
                     "recommended_action": "increase_correction or emergency_land"},
                ))
                if self._critical_unack_since is None:
                    self._critical_unack_since = step
        elif deviation > self.deviation_warn_m:
            self._consecutive_deviations += 1
            if self._consecutive_deviations >= 3 and self._should_fire(AlertType.DEVIATION_WARNING, step, cooldown=15):
                alerts.append(self._create_alert(
                    AlertType.DEVIATION_WARNING, "WARNING", state,
                    {"deviation_m": round(deviation, 1),
                     "consecutive_checks": self._consecutive_deviations},
                ))
        else:
            self._consecutive_deviations = 0

        # 2. Block mismatch persistence
        if not is_match:
            self._consecutive_mismatches += 1
            if self._consecutive_mismatches >= 5 and self._should_fire(AlertType.BLOCK_MISMATCH_PERSISTENT, step, cooldown=25):
                alerts.append(self._create_alert(
                    AlertType.BLOCK_MISMATCH_PERSISTENT, "WARNING", state,
                    {"mismatch_count": self._consecutive_mismatches,
                     "correction_count": state.get("autopilot", {}).get("cumulative_corrections", 0)},
                ))
        else:
            self._consecutive_mismatches = 0

        # 3. Stall detection
        if block_index == self._last_block_index:
            self._stall_counter += self.check_interval
            if self._stall_counter >= self.stall_threshold_steps and self._should_fire(AlertType.STALL_DETECTED, step, cooldown=40):
                alerts.append(self._create_alert(
                    AlertType.STALL_DETECTED, "WARNING", state,
                    {"steps_stalled": self._stall_counter,
                     "current_block_index": block_index,
                     "progress_pct": progress},
                ))
        else:
            self._stall_counter = 0
            self._last_block_index = block_index

        # 4. Weather checks
        if wind_speed > self.wind_extreme_mps or turbulence > self.turbulence_extreme:
            if self._should_fire(AlertType.WEATHER_EXTREME, step, cooldown=25):
                alerts.append(self._create_alert(
                    AlertType.WEATHER_EXTREME, "CRITICAL", state,
                    {"wind_speed_mps": round(wind_speed, 2),
                     "turbulence": round(turbulence, 3),
                     "recommended_action": "emergency_land"},
                ))
                if self._critical_unack_since is None:
                    self._critical_unack_since = step
        elif wind_speed > self.wind_warn_mps or turbulence > self.turbulence_warn:
            if self._should_fire(AlertType.WEATHER_HAZARD, step, cooldown=20):
                alerts.append(self._create_alert(
                    AlertType.WEATHER_HAZARD, "WARNING", state,
                    {"wind_speed_mps": round(wind_speed, 2),
                     "turbulence": round(turbulence, 3)},
                ))

        # 5. Conformance check
        if self.sim.ledger:
            conf = self.sim.ledger.get_conformance_score()
            if conf["score"] < self.conformance_warn and conf["total_events"] > 10:
                if self._should_fire(AlertType.CONFORMANCE_DEGRADING, step, cooldown=40):
                    alerts.append(self._create_alert(
                        AlertType.CONFORMANCE_DEGRADING, "WARNING", state,
                        {"conformance_score": round(conf["score"], 3),
                         "total_events": conf["total_events"],
                         "deviations": conf["deviations"]},
                    ))

        # 6. Milestones
        if progress >= 25 and not self._milestone_25:
            self._milestone_25 = True
            alerts.append(self._create_alert(
                AlertType.FLIGHT_MILESTONE, "INFO", state,
                {"progress_pct": round(progress, 1), "milestone": "25%"},
            ))
        if progress >= 50 and not self._milestone_50:
            self._milestone_50 = True
            alerts.append(self._create_alert(
                AlertType.FLIGHT_MILESTONE, "INFO", state,
                {"progress_pct": round(progress, 1), "milestone": "50%"},
            ))
        if progress >= 75 and not self._milestone_75:
            self._milestone_75 = True
            alerts.append(self._create_alert(
                AlertType.FLIGHT_MILESTONE, "INFO", state,
                {"progress_pct": round(progress, 1), "milestone": "75%"},
            ))

        # 7. Flight complete
        if state.get("status") == "COMPLETE":
            alerts.append(self._create_alert(
                AlertType.FLIGHT_COMPLETE, "INFO", state,
                {"total_steps": state.get("step", 0),
                 "elapsed_s": state.get("elapsed_seconds", 0),
                 "conformance_score": self.sim.ledger.get_conformance_score()["score"]
                 if self.sim.ledger else 0},
            ))

        for a in alerts:
            self.alerts.append(a)
        return alerts

    def get_telemetry_summary(self) -> EdgeTelemetrySummary:
        """Aggregate recent telemetry for AI consumption."""
        buffer = self._tick_buffer[-100:]  # Last 100 ticks
        if not buffer:
            return self._empty_summary()

        deviations = [t.get("deviation_meters", 0) for t in buffer]
        matches = [1 if t.get("is_match", False) else 0 for t in buffer]
        wind_speeds = [t.get("environment", {}).get("wind_speed_mps", 0) for t in buffer]
        turbulences = [t.get("environment", {}).get("turbulence_intensity", 0) for t in buffer]
        corrections = sum(1 for t in buffer if t.get("autopilot", {}).get("correction_applied", False))

        first_block = buffer[0].get("block_index", 0)
        last_block = buffer[-1].get("block_index", 0)
        conf = self.sim.ledger.get_conformance_score() if self.sim.ledger else {"score": 1.0}

        return EdgeTelemetrySummary(
            flight_id=self.sim.flight_id,
            window_steps=len(buffer),
            avg_deviation_m=statistics.mean(deviations) if deviations else 0,
            max_deviation_m=max(deviations) if deviations else 0,
            block_match_rate=statistics.mean(matches) if matches else 1.0,
            blocks_traversed=last_block - first_block,
            current_block_index=last_block,
            total_blocks=len(self.sim.rail),
            corrections_in_window=corrections,
            avg_wind_speed=statistics.mean(wind_speeds) if wind_speeds else 0,
            max_wind_speed=max(wind_speeds) if wind_speeds else 0,
            avg_turbulence=statistics.mean(turbulences) if turbulences else 0,
            conformance_score=conf["score"],
            progress_percent=buffer[-1].get("progress_percent", 0),
            active_alerts=len([a for a in self.alerts if not a.acknowledged]),
            pending_alerts=len(self.get_pending_alerts()),
            elapsed_seconds=buffer[-1].get("elapsed_seconds", 0),
        )

    def get_pending_alerts(self) -> List[EdgeAlert]:
        """Get unacknowledged alerts."""
        return [a for a in self.alerts if not a.acknowledged]

    def acknowledge_alert(self, alert_id: str, resolution: str) -> bool:
        """AI marks an alert as handled."""
        for a in self.alerts:
            if a.alert_id == alert_id:
                a.acknowledged = True
                a.resolution = resolution
                # Clear critical escalation timer if this was the critical one
                if a.severity == "CRITICAL":
                    self._critical_unack_since = None
                return True
        return False

    def set_thresholds(self, **kwargs) -> Dict[str, Any]:
        """AI can adjust edge thresholds."""
        updated = {}
        for key, val in kwargs.items():
            if hasattr(self, key) and isinstance(val, (int, float)):
                setattr(self, key, val)
                updated[key] = val
        return {"updated_thresholds": updated}

    def get_status(self) -> Dict[str, Any]:
        """Edge computer health status."""
        return {
            "layer": "edge_computer",
            "status": "MONITORING" if self.sim.is_active else "IDLE",
            "checks_performed": self._checks_performed,
            "total_alerts": len(self.alerts),
            "pending_alerts": len(self.get_pending_alerts()),
            "thresholds": {
                "deviation_warn_m": self.deviation_warn_m,
                "deviation_critical_m": self.deviation_critical_m,
                "wind_warn_mps": self.wind_warn_mps,
                "conformance_warn": self.conformance_warn,
            },
        }

    # Internal helpers

    def _create_alert(self, alert_type: str, severity: str, state: Dict, data: Dict) -> EdgeAlert:
        return EdgeAlert(
            alert_id=f"ALT-{uuid.uuid4().hex[:8].upper()}",
            alert_type=alert_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc).isoformat(),
            flight_id=self.sim.flight_id,
            step=state.get("step", 0),
            position=state.get("position", {}),
            data=data,
            message=ALERT_MESSAGES.get(alert_type, alert_type),
        )

    def _should_fire(self, alert_type: str, step: int, cooldown: int) -> bool:
        """Prevent alert spam — enforce cooldown between same type."""
        last = self._recent_alert_types.get(alert_type, -999)
        if step - last < cooldown:
            return False
        self._recent_alert_types[alert_type] = step
        return True

    def _empty_summary(self) -> EdgeTelemetrySummary:
        return EdgeTelemetrySummary(
            flight_id=self.sim.flight_id,
            window_steps=0, avg_deviation_m=0, max_deviation_m=0,
            block_match_rate=1.0, blocks_traversed=0,
            current_block_index=0, total_blocks=len(self.sim.rail),
            corrections_in_window=0, avg_wind_speed=0, max_wind_speed=0,
            avg_turbulence=0, conformance_score=1.0, progress_percent=0,
            active_alerts=0, pending_alerts=0, elapsed_seconds=0,
        )
