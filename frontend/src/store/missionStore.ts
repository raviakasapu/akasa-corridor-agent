import { create } from "zustand";
import type {
  Mission,
  MissionStatus,
  Drone,
  Corridor,
  AgentEvent,
  Agent,
  ToolCall,
  ToolResult,
  EventType,
  EdgeAlert,
  EdgeTelemetry,
} from "../types";

interface MissionState {
  // Connection
  isConnected: boolean;
  setConnected: (v: boolean) => void;

  // Mission
  mission: Mission;
  setMissionStatus: (status: MissionStatus) => void;
  setJobId: (id: string) => void;
  setMode: (mode: Mission["mode"]) => void;
  resetMission: () => void;

  // Drone
  drone: Drone | null;
  flightTrail: [number, number][];
  updateDrone: (d: Partial<Drone>) => void;

  // Corridor
  corridor: Corridor | null;
  setCorridor: (c: Corridor) => void;

  // Edge Computer
  edgeAlerts: EdgeAlert[];
  edgeTelemetry: EdgeTelemetry | null;
  addEdgeAlert: (a: EdgeAlert) => void;
  setEdgeTelemetry: (t: EdgeTelemetry) => void;

  // Events
  events: AgentEvent[];
  addEvent: (e: AgentEvent) => void;
  clearEvents: () => void;

  // Agent
  agent: Agent;
  updateAgent: (a: Partial<Agent>) => void;
  addToolCall: (tc: ToolCall) => void;
  addToolResult: (tr: ToolResult) => void;
  setAgentContent: (text: string) => void;
  setAgentThinking: (text: string) => void;

  // Selectors
  recentEvents: () => AgentEvent[];
}

const defaultAgent: Agent = {
  name: "AkasaCorridorAgent",
  mode: "single",
  status: "idle",
  thinking: "",
  toolCalls: [],
  toolResults: [],
  content: "",
  iterations: 0,
  totalToolCalls: 0,
  durationS: 0,
};

const defaultMission: Mission = {
  jobId: "",
  status: "idle",
  mode: "single",
  startTime: null,
  agents: [],
  stats: {
    corridorsCreated: 0,
    flightsCompleted: 0,
    toolCalls: 0,
    durationS: 0,
    conformanceScore: null,
    certificateId: null,
  },
};

export const useMissionStore = create<MissionState>((set, get) => ({
  isConnected: false,
  setConnected: (v) => set({ isConnected: v }),

  mission: { ...defaultMission },
  setMissionStatus: (status) =>
    set((s) => ({
      mission: {
        ...s.mission,
        status,
        startTime: status === "running" ? Date.now() : s.mission.startTime,
      },
    })),
  setJobId: (id) =>
    set((s) => ({ mission: { ...s.mission, jobId: id } })),
  setMode: (mode) =>
    set((s) => ({ mission: { ...s.mission, mode } })),
  resetMission: () =>
    set({
      mission: { ...defaultMission },
      drone: null,
      flightTrail: [],
      corridor: null,
      edgeAlerts: [],
      edgeTelemetry: null,
      events: [],
      agent: { ...defaultAgent },
    }),

  drone: null,
  flightTrail: [],
  updateDrone: (d) =>
    set((s) => {
      const updated = s.drone ? { ...s.drone, ...d } : (d as Drone);
      const trail = [...s.flightTrail];
      if (updated.position && updated.position.lat !== 0) {
        trail.push([updated.position.lat, updated.position.lon]);
      }
      return { drone: updated, flightTrail: trail };
    }),

  corridor: null,
  setCorridor: (c) => set({ corridor: c }),

  edgeAlerts: [],
  edgeTelemetry: null,
  addEdgeAlert: (a) =>
    set((s) => ({ edgeAlerts: [...s.edgeAlerts, a].slice(-50) })),
  setEdgeTelemetry: (t) => set({ edgeTelemetry: t }),

  events: [],
  addEvent: (e) =>
    set((s) => ({ events: [...s.events, e].slice(-200) })),
  clearEvents: () => set({ events: [] }),

  agent: { ...defaultAgent },
  updateAgent: (a) =>
    set((s) => ({ agent: { ...s.agent, ...a } })),
  addToolCall: (tc) =>
    set((s) => ({
      agent: {
        ...s.agent,
        toolCalls: [...s.agent.toolCalls, tc],
        status: "executing",
      },
    })),
  addToolResult: (tr) =>
    set((s) => ({
      agent: {
        ...s.agent,
        toolResults: [...s.agent.toolResults, tr],
        totalToolCalls: s.agent.totalToolCalls + 1,
      },
      mission: {
        ...s.mission,
        stats: {
          ...s.mission.stats,
          toolCalls: s.mission.stats.toolCalls + 1,
        },
      },
    })),
  setAgentContent: (text) =>
    set((s) => ({ agent: { ...s.agent, content: text } })),
  setAgentThinking: (text) =>
    set((s) => ({ agent: { ...s.agent, thinking: text, status: "thinking" } })),

  recentEvents: () => get().events.slice(-50),
}));
