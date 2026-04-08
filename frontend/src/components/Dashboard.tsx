import { useMission } from "../hooks/useMission";
import { useMissionStore } from "../store/missionStore";
import { DroneMap } from "./DroneMap";
import { EdgePanel } from "./EdgePanel";
import { EventFeed } from "./EventFeed";
import { AgentPanel } from "./AgentPanel";
import { MissionControl } from "./MissionControl";
import { ToolExecutor } from "./ToolExecutor";
import { Navigation, Shield, Cpu, FileCheck } from "lucide-react";

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
  const edgeAlerts = useMissionStore((s) => s.edgeAlerts);
  const edgeTelemetry = useMissionStore((s) => s.edgeTelemetry);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="px-6 py-2 border-b border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <Navigation className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-gray-900 font-bold text-sm">Akasa Corridor Agent</h1>
              <p className="text-gray-400 text-[10px]">3-Layer Architecture: Autopilot / Edge / AI Commander</p>
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
                      : drone.status === "COMPLETE"
                      ? "text-green-700 font-medium"
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
        </div>

        {/* 3-Layer Status Strip */}
        <div className="flex items-center gap-6 mt-1.5 text-[10px] text-gray-400">
          <div className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
            <span className="font-medium text-gray-500">Autopilot</span>
            {drone?.autopilot && <span>Corrections: {drone.autopilot.cumulative_corrections}</span>}
          </div>
          <div className="flex items-center gap-1">
            {edgeTelemetry ? (
              <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-gray-300" />
            )}
            <span className="font-medium text-gray-500">Edge</span>
            {edgeAlerts.length > 0 && <span>Alerts: {edgeAlerts.filter(a => !a.acknowledged).length} pending</span>}
          </div>
          <div className="flex items-center gap-1">
            <span className={`h-1.5 w-1.5 rounded-full ${agent.status === "thinking" || agent.status === "executing" ? "bg-blue-500 animate-pulse" : agent.status === "complete" ? "bg-green-500" : "bg-gray-300"}`} />
            <span className="font-medium text-gray-500">AI Commander</span>
            {agent.totalToolCalls > 0 && <span>Decisions: {agent.totalToolCalls}</span>}
          </div>
        </div>
      </header>

      {/* Main layout: 3 columns */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Map + Controls */}
        <div className="flex-[2] flex flex-col p-3 gap-3 overflow-y-auto">
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

        {/* Center: Edge Computer Panel */}
        <div className="w-[280px] flex flex-col p-3 pl-0 gap-3">
          <EdgePanel alerts={edgeAlerts} telemetry={edgeTelemetry} />
        </div>

        {/* Right: AI Commander + Events */}
        <div className="flex-[1] flex flex-col p-3 pl-0 gap-3 min-w-[320px] max-w-[400px]">
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
