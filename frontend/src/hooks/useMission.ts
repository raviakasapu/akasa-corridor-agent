import { useCallback } from "react";
import { useMissionStore } from "../store/missionStore";
import { useWebSocket } from "./useWebSocket";
import { send } from "../utils/websocket";
import { EventType } from "../types";
import type { AgentEvent, ToolCall, ToolResult, Drone, EdgeAlert, EdgeTelemetry } from "../types";

export function useMission() {
  const store = useMissionStore();

  const handleEvent = useCallback(
    (event: AgentEvent) => {
      store.addEvent(event);

      switch (event.event) {
        case EventType.Connected:
          store.setConnected(true);
          break;

        case EventType.ContextSet:
          break;

        case EventType.Status:
          store.updateAgent({ status: "thinking" });
          store.setMissionStatus("running");
          break;

        case EventType.Thinking:
          store.setAgentThinking(
            (event.data.message as string) || "Processing..."
          );
          break;

        case EventType.ToolCall: {
          const tc: ToolCall = {
            tool: (event.data.tool as string) || "",
            args: (event.data.args as Record<string, unknown>) || {},
            toolIndex: (event.data.tool_index as number) || 0,
            toolId: (event.data.tool_id as string) || "",
          };
          store.addToolCall(tc);
          break;
        }

        case EventType.ToolDone: {
          // Parse result — framework may send it as a JSON string or object
          let rawResult = event.data.result;
          if (typeof rawResult === "string") {
            try {
              rawResult = JSON.parse(rawResult);
            } catch {
              rawResult = {};
            }
          }
          const parsedResult = (rawResult as Record<string, unknown>) || {};

          const tr: ToolResult = {
            tool: (event.data.tool as string) || "",
            success: (event.data.success as boolean) ?? true,
            summary: (event.data.summary as string) || "",
            result: parsedResult,
            toolId: (event.data.tool_id as string) || "",
          };
          store.addToolResult(tr);

          // Debug: log simulation tool results
          if (
            tr.tool === "step_simulation" ||
            tr.tool === "check_block_membership" ||
            tr.tool === "create_corridor"
          ) {
            console.log(`[useMission] ${tr.tool} result:`, parsedResult);
          }

          // Extract drone state from simulation tools
          const result = tr.result;
          if (
            tr.tool === "check_block_membership" ||
            tr.tool === "step_simulation" ||
            tr.tool === "get_drone_position" ||
            tr.tool === "start_simulation"
          ) {
            if (result.flight_id) {
              const drone: Partial<Drone> = {
                flightId: result.flight_id as string,
                status: (result.status as Drone["status"]) || "NOMINAL",
              };
              // Position may be in "position" or "start_position" field
              const posData = result.position || result.start_position;
              if (posData && typeof posData === "object") {
                const pos = posData as Record<string, number>;
                drone.position = {
                  lat: pos.lat,
                  lon: pos.lon,
                  alt: pos.alt || 100,
                };
              }
              if (result.assigned_block)
                drone.assignedBlock = result.assigned_block as string;
              if (result.current_block)
                drone.currentBlock = result.current_block as string;
              if (result.block_index !== undefined)
                drone.blockIndex = result.block_index as number;
              if (result.total_blocks !== undefined)
                drone.totalBlocks = result.total_blocks as number;
              if (result.deviation_meters !== undefined)
                drone.deviationMeters = result.deviation_meters as number;
              store.updateDrone(drone);
            }
          }

          // Extract corridor from create_corridor
          if (tr.tool === "create_corridor" && result.corridor_id) {
            const start = result.start as Record<string, number> | undefined;
            const end = result.end as Record<string, number> | undefined;
            store.setCorridor({
              corridorId: result.corridor_id as string,
              name: (result.name as string) || "",
              start: start
                ? { lat: start.lat, lon: start.lon, alt: start.alt || 0 }
                : { lat: 0, lon: 0, alt: 0 },
              end: end
                ? { lat: end.lat, lon: end.lon, alt: end.alt || 0 }
                : { lat: 0, lon: 0, alt: 0 },
              blockCount: (result.block_count as number) || 0,
              resolution: (result.resolution as number) || 10,
              rail: (result.rail as string[]) || [],
            });
            store.setMissionStatus("running");
          }

          // Extract certificate
          if (tr.tool === "generate_certificate" && result.certificate_id) {
            store.setMissionStatus("complete");
          }
          break;
        }

        case EventType.Content:
          store.setAgentContent((event.data.text as string) || "");
          store.updateAgent({ status: "complete" });
          break;

        case EventType.Complete:
          store.updateAgent({
            status: "complete",
            iterations: (event.data.iterations as number) || 0,
            durationS: (event.data.duration_s as number) || 0,
          });
          store.setMissionStatus("complete");
          break;

        case EventType.Error:
          store.updateAgent({
            status: "error",
            content: (event.data.message as string) || "Unknown error",
          });
          store.setMissionStatus("error");
          break;

        case EventType.SimulationTick: {
          // Real-time position update from background simulation
          const tickData = event.data;
          if (tickData.flight_id || tickData.position) {
            const drone: Partial<Drone> = {};
            if (tickData.flight_id) drone.flightId = tickData.flight_id as string;
            if (tickData.status) drone.status = tickData.status as Drone["status"];
            if (tickData.position && typeof tickData.position === "object") {
              const pos = tickData.position as Record<string, number>;
              drone.position = { lat: pos.lat, lon: pos.lon, alt: pos.alt || 100 };
            }
            if (tickData.assigned_block) drone.assignedBlock = tickData.assigned_block as string;
            if (tickData.current_block) drone.currentBlock = tickData.current_block as string;
            if (tickData.block_index !== undefined) drone.blockIndex = tickData.block_index as number;
            if (tickData.total_blocks !== undefined) drone.totalBlocks = tickData.total_blocks as number;
            if (tickData.deviation_meters !== undefined) drone.deviationMeters = tickData.deviation_meters as number;
            if (tickData.progress_percent !== undefined) drone.progressPercent = tickData.progress_percent as number;
            if (tickData.elapsed_seconds !== undefined) drone.elapsedSeconds = tickData.elapsed_seconds as number;
            if (tickData.environment) drone.environment = tickData.environment as Drone["environment"];
            if (tickData.autopilot) drone.autopilot = tickData.autopilot as Drone["autopilot"];
            store.updateDrone(drone);
          }
          break;
        }

        case EventType.EdgeAlert: {
          const ad = event.data;
          const alert: EdgeAlert = {
            alertId: (ad.alert_id as string) || "",
            alertType: (ad.alert_type as string) || "",
            severity: (ad.severity as EdgeAlert["severity"]) || "INFO",
            timestamp: (ad.timestamp as string) || "",
            flightId: (ad.flight_id as string) || "",
            step: (ad.step as number) || 0,
            data: (ad.data as Record<string, unknown>) || {},
            message: (ad.message as string) || "",
            acknowledged: false,
          };
          store.addEdgeAlert(alert);
          break;
        }

        case EventType.EdgeTelemetry: {
          const td = event.data;
          const telem: EdgeTelemetry = {
            flightId: (td.flight_id as string) || "",
            avgDeviationM: (td.avg_deviation_m as number) || 0,
            maxDeviationM: (td.max_deviation_m as number) || 0,
            blockMatchRate: (td.block_match_rate as number) || 1,
            conformanceScore: (td.conformance_score as number) || 1,
            progressPercent: (td.progress_percent as number) || 0,
            activeAlerts: (td.active_alerts as number) || 0,
            pendingAlerts: (td.pending_alerts as number) || 0,
            avgWindSpeed: (td.avg_wind_speed as number) || 0,
            maxWindSpeed: (td.max_wind_speed as number) || 0,
            elapsedSeconds: (td.elapsed_seconds as number) || 0,
          };
          store.setEdgeTelemetry(telem);
          break;
        }

        case EventType.SimulationUpdated:
          break;
      }
    },
    [store]
  );

  useWebSocket(handleEvent);

  const startMission = useCallback(
    (jobId: string, message: string, mode: string = "single") => {
      store.resetMission();
      store.setJobId(jobId);
      store.setMode(mode as "single");
      store.setMissionStatus("running");

      send({ action: "set_context", job_id: jobId, mode });
      setTimeout(() => {
        send({ action: "execute", job_id: jobId, message });
      }, 100);
    },
    [store]
  );

  return {
    mission: store.mission,
    drone: store.drone,
    corridor: store.corridor,
    agent: store.agent,
    events: store.events,
    isConnected: store.isConnected,
    startMission,
    reset: store.resetMission,
  };
}
