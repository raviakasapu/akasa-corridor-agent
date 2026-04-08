import { useMission } from "../hooks/useMission";
import { useMissionStore } from "../store/missionStore";
import { DroneMap } from "./DroneMap";
import { EventFeed } from "./EventFeed";
import { AgentPanel } from "./AgentPanel";
import { MissionControl } from "./MissionControl";
import { ToolExecutor } from "./ToolExecutor";
import { Navigation, Shield, FileCheck } from "lucide-react";

export function Dashboard() {
  const {
    mission,
    drone,
    corridor,
    agent,
    events,
    isConnected,
    startMission,
    reset,
  } = useMission();

  const flightTrail = useMissionStore((s) => s.flightTrail);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="px-6 py-3 border-b border-gray-200 flex items-center justify-between bg-white shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Navigation className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-gray-900 font-bold text-sm">Akasa Corridor Agent</h1>
            <p className="text-gray-400 text-xs">Drone corridor management</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs text-gray-500">
          {corridor && (
            <div className="flex items-center gap-1">
              <Shield className="w-3 h-3 text-cyan-600" />
              <span>{corridor.corridorId}</span>
              <span className="text-gray-400">({corridor.blockCount} blocks)</span>
            </div>
          )}
          {drone && (
            <div className="flex items-center gap-1">
              <Navigation className="w-3 h-3 text-blue-600" />
              <span>{drone.flightId}</span>
              <span
                className={
                  drone.status === "NOMINAL"
                    ? "text-green-600 font-medium"
                    : drone.status === "DEVIATING"
                    ? "text-red-600 font-medium"
                    : "text-gray-500"
                }
              >
                {drone.status}
              </span>
            </div>
          )}
          {mission.stats.certificateId && (
            <div className="flex items-center gap-1">
              <FileCheck className="w-3 h-3 text-green-600" />
              <span className="text-green-600">{mission.stats.certificateId}</span>
            </div>
          )}
        </div>
      </header>

      {/* Main layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Map + Controls */}
        <div className="flex-[2] flex flex-col p-4 gap-4 overflow-y-auto">
          <MissionControl
            isConnected={isConnected}
            missionStatus={mission.status}
            onStart={startMission}
            onReset={reset}
          />
          <div className="flex-1 min-h-[400px]">
            <DroneMap drone={drone} corridor={corridor} flightTrail={flightTrail} />
          </div>
        </div>

        {/* Right: Agent + Events */}
        <div className="flex-[1] flex flex-col p-4 pl-0 gap-4 min-w-[360px] max-w-[440px]">
          <AgentPanel agent={agent} />
          <ToolExecutor
            toolCalls={agent.toolCalls}
            toolResults={agent.toolResults}
          />
          <div className="flex-1 min-h-0">
            <EventFeed events={events} />
          </div>
        </div>
      </div>
    </div>
  );
}
