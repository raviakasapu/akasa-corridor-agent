import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { formatTime } from "../utils/formatters";
import { EventType } from "../types";
import type { AgentEvent } from "../types";

const eventStyle: Record<string, { border: string; label: string; color: string }> = {
  [EventType.Status]: { border: "border-gray-500", label: "Status", color: "text-gray-400" },
  [EventType.Thinking]: { border: "border-purple-500", label: "Think", color: "text-purple-400" },
  [EventType.ToolCall]: { border: "border-blue-500", label: "Tool", color: "text-blue-400" },
  [EventType.ToolDone]: { border: "border-green-500", label: "Done", color: "text-green-400" },
  [EventType.Content]: { border: "border-white/30", label: "Agent", color: "text-white" },
  [EventType.Complete]: { border: "border-green-500", label: "Complete", color: "text-green-400" },
  [EventType.Error]: { border: "border-red-500", label: "Error", color: "text-red-400" },
  [EventType.SimulationUpdated]: { border: "border-yellow-500", label: "Sim", color: "text-yellow-400" },
};

function eventSummary(e: AgentEvent): string {
  const d = e.data;
  switch (e.event) {
    case EventType.Status:
      return (d.message as string) || "Starting...";
    case EventType.Thinking:
      return (d.message as string) || "Processing...";
    case EventType.ToolCall:
      return `${d.tool}(${JSON.stringify(d.args || {}).slice(0, 60)})`;
    case EventType.ToolDone:
      return `${d.tool} ${d.success ? "OK" : "FAIL"}: ${(d.summary as string)?.slice(0, 80) || ""}`;
    case EventType.Content:
      return ((d.text as string) || "").slice(0, 120);
    case EventType.Complete:
      return `${d.tool_calls} tools, ${((d.duration_s as number) || 0).toFixed(1)}s`;
    case EventType.Error:
      return (d.message as string) || "Unknown error";
    case EventType.SimulationUpdated:
      return `Updated: ${d.tool}`;
    default:
      return JSON.stringify(d).slice(0, 80);
  }
}

export function EventFeed({ events }: { events: AgentEvent[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events]);

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden flex flex-col h-full">
      <div className="px-4 py-3 bg-gray-900/80 border-b border-gray-800 flex items-center justify-between">
        <span className="text-white font-medium text-sm">Event Feed</span>
        <span className="text-xs text-gray-500">{events.length} events</span>
      </div>
      <div ref={ref} className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-xs">
        <AnimatePresence initial={false}>
          {events.map((e, i) => {
            const style = eventStyle[e.event] || eventStyle[EventType.Status];
            return (
              <motion.div
                key={`${e.timestamp}-${i}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={`border-l-2 ${style.border} pl-2 py-0.5`}
              >
                <span className="text-gray-600 mr-2">{formatTime(e.timestamp)}</span>
                <span className={`${style.color} mr-1`}>{style.label}</span>
                <span className="text-gray-300">{eventSummary(e)}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
        {events.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-600">
            Waiting for events...
          </div>
        )}
      </div>
    </div>
  );
}
