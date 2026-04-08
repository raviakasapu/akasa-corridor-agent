// Agent event types matching backend WebSocket protocol
export enum EventType {
  Connected = "connected",
  ContextSet = "context_set",
  Status = "status",
  Thinking = "thinking",
  ToolCall = "tool_call",
  ToolDone = "tool_done",
  Content = "content",
  Complete = "complete",
  Error = "error",
  SimulationUpdated = "simulation_updated",
  Pong = "pong",
}

export interface Position {
  lat: number;
  lon: number;
  alt: number;
}

export interface Drone {
  flightId: string;
  corridorId: string;
  position: Position;
  assignedBlock: string;
  currentBlock: string;
  blockIndex: number;
  totalBlocks: number;
  status: "NOMINAL" | "DEVIATING" | "COMPLETE" | "EMERGENCY";
  speed: number;
  deviationMeters: number;
}

export interface Corridor {
  corridorId: string;
  name: string;
  start: Position;
  end: Position;
  blockCount: number;
  resolution: number;
  rail: string[];
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  toolIndex: number;
  toolId: string;
}

export interface ToolResult {
  tool: string;
  success: boolean;
  summary: string;
  result: Record<string, unknown>;
  toolId: string;
}

export interface AgentEvent {
  event: EventType;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface Agent {
  name: string;
  mode: string;
  status: "idle" | "thinking" | "executing" | "complete" | "error";
  thinking: string;
  toolCalls: ToolCall[];
  toolResults: ToolResult[];
  content: string;
  iterations: number;
  totalToolCalls: number;
  durationS: number;
}

export type MissionStatus =
  | "idle"
  | "connecting"
  | "running"
  | "complete"
  | "error";

export interface MissionStats {
  corridorsCreated: number;
  flightsCompleted: number;
  toolCalls: number;
  durationS: number;
  conformanceScore: number | null;
  certificateId: string | null;
}

export interface Mission {
  jobId: string;
  status: MissionStatus;
  mode: "single" | "guardian" | "designer" | "compliance";
  startTime: number | null;
  agents: Agent[];
  stats: MissionStats;
}
