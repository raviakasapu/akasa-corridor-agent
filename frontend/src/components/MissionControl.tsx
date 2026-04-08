import { useState } from "react";
import { Play, RotateCcw, Wifi, WifiOff } from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import type { MissionStatus } from "../types";

interface Props {
  isConnected: boolean;
  missionStatus: MissionStatus;
  onStart: (jobId: string, message: string, mode: string) => void;
  onReset: () => void;
}

const PRESETS = [
  {
    label: "Full Mission (SF to Oakland)",
    message:
      "Execute a complete corridor mission as Mission Commander:\n1. Create a corridor from San Francisco (37.7749, -122.4194) to Oakland (37.8044, -122.2712) at resolution 10, validate it.\n2. Start the simulation — the drone flies autonomously with autopilot and the Edge Computer monitors it.\n3. Periodically call get_edge_status to check the strategic overview. Call get_pending_alerts to review any alerts from the edge. For each alert, decide on action and acknowledge it.\n4. When the flight completes (FLIGHT_COMPLETE alert), call complete_flight, verify chain integrity, calculate conformance, and generate certificate.\n5. Provide a mission summary.",
  },
  {
    label: "Quick Demo (Bay Bridge)",
    message:
      "Create a corridor 'Bay Bridge' from SF (37.7875, -122.3908) to Treasure Island (37.8235, -122.3708) at resolution 11. Validate it. Start simulation. The Edge Computer monitors autonomously — check get_edge_status and get_pending_alerts a few times, acknowledge alerts, then complete the flight and certify.",
  },
  {
    label: "Create Corridor Only",
    message:
      "Create a corridor named 'Demo Corridor' from Delhi (28.6139, 77.2090) to Agra (27.1767, 78.0081) at H3 resolution 10. Then validate the corridor.",
  },
  {
    label: "List Corridors",
    message: "List all existing corridors.",
  },
];

export function MissionControl({ isConnected, missionStatus, onStart, onReset }: Props) {
  const [message, setMessage] = useState(PRESETS[0].message);
  const [mode, setMode] = useState("single");
  const isRunning = missionStatus === "running";

  const handleStart = () => {
    const jobId = `mission-${Date.now().toString(36)}`;
    onStart(jobId, message, mode);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-gray-800 font-semibold text-sm">Mission Control</h2>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Wifi className="w-4 h-4 text-green-500" />
          ) : (
            <WifiOff className="w-4 h-4 text-red-500" />
          )}
          <StatusBadge status={missionStatus} />
        </div>
      </div>

      <div className="flex gap-2">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:border-blue-400"
        >
          <option value="single">Single Agent</option>
          <option value="guardian">Guardian Only</option>
          <option value="designer">Designer Only</option>
          <option value="compliance">Compliance Only</option>
        </select>
        <select
          onChange={(e) => setMessage(PRESETS[Number(e.target.value)].message)}
          className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 flex-1 focus:outline-none focus:border-blue-400"
        >
          {PRESETS.map((p, i) => (
            <option key={i} value={i}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={3}
        className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700 resize-none focus:outline-none focus:border-blue-400"
        placeholder="Enter mission instructions..."
      />

      <div className="flex gap-2">
        <button
          onClick={handleStart}
          disabled={!isConnected || isRunning || !message.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 rounded-lg text-sm font-medium text-white transition"
        >
          <Play className="w-4 h-4" />
          {isRunning ? "Running..." : "Start Mission"}
        </button>
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-lg text-sm text-gray-600 transition"
        >
          <RotateCcw className="w-4 h-4" />
          Reset
        </button>
      </div>
    </div>
  );
}
