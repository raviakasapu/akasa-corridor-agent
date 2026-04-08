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
    label: "Full Mission (SF → Oakland)",
    message:
      "Execute a complete mission: create a corridor from San Francisco (37.7749, -122.4194) to Oakland (37.8044, -122.2712) at resolution 10, validate it, start a simulation, monitor 6 cycles checking block membership each time, complete the flight, verify chain integrity, and generate a compliance certificate.",
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
    <div className="bg-gray-900/50 rounded-xl border border-gray-800 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-white font-medium text-sm">Mission Control</h2>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Wifi className="w-4 h-4 text-green-400" />
          ) : (
            <WifiOff className="w-4 h-4 text-red-400" />
          )}
          <StatusBadge status={missionStatus} />
        </div>
      </div>

      <div className="flex gap-2">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white"
        >
          <option value="single">Single Agent</option>
          <option value="guardian">Guardian Only</option>
          <option value="designer">Designer Only</option>
          <option value="compliance">Compliance Only</option>
        </select>
        <select
          onChange={(e) => setMessage(PRESETS[Number(e.target.value)].message)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white flex-1"
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
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 resize-none focus:outline-none focus:border-blue-500"
        placeholder="Enter mission instructions..."
      />

      <div className="flex gap-2">
        <button
          onClick={handleStart}
          disabled={!isConnected || isRunning || !message.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium text-white transition"
        >
          <Play className="w-4 h-4" />
          {isRunning ? "Running..." : "Start Mission"}
        </button>
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition"
        >
          <RotateCcw className="w-4 h-4" />
          Reset
        </button>
      </div>
    </div>
  );
}
