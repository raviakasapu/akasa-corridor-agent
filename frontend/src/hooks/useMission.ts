import { useCallback } from "react";
import { useMissionStore } from "../store/missionStore";
import { useWebSocket } from "./useWebSocket";
import { send } from "../utils/websocket";
import { EventType } from "../types";
import type { AgentEvent, ToolCall, ToolResult, Drone } from "../types";

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
          const tr: ToolResult = {
            tool: (event.data.tool as string) || "",
            success: (event.data.success as boolean) ?? true,
            summary: (event.data.summary as string) || "",
            result: (event.data.result as Record<string, unknown>) || {},
            toolId: (event.data.tool_id as string) || "",
          };
          store.addToolResult(tr);

          // Extract drone state from simulation tools
          const result = tr.result;
          if (
            tr.tool === "check_block_membership" ||
            tr.tool === "step_simulation" ||
            tr.tool === "get_drone_position"
          ) {
            if (result.flight_id) {
              const drone: Partial<Drone> = {
                flightId: result.flight_id as string,
                status: (result.status as Drone["status"]) || "NOMINAL",
              };
              if (result.position && typeof result.position === "object") {
                const pos = result.position as Record<string, number>;
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
            store.setCorridor({
              corridorId: result.corridor_id as string,
              name: (result.name as string) || "",
              start: { lat: 0, lon: 0, alt: 0 },
              end: { lat: 0, lon: 0, alt: 0 },
              blockCount: (result.block_count as number) || 0,
              resolution: (result.resolution as number) || 10,
              rail: [],
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

        case EventType.SimulationUpdated:
          // Trigger map refresh — drone state already updated via tool_done
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
