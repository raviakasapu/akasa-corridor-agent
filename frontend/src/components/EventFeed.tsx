import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { formatTime } from "../utils/formatters";
import { EventType } from "../types";
import type { AgentEvent } from "../types";

const eventStyle: Record<string, { border: string; label: string; color: string }> = {
  [EventType.Status]: { border: "border-gray-400", label: "Status", color: "text-gray-500" },
  [EventType.Thinking]: { border: "border-purple-400", label: "Think", color: "text-purple-600" },
  [EventType.ToolCall]: { border: "border-blue-400", label: "Tool", color: "text-blue-600" },
  [EventType.ToolDone]: { border: "border-green-400", label: "Done", color: "text-green-600" },
  [EventType.Content]: { border: "border-gray-600", label: "Agent", color: "text-gray-700" },
  [EventType.Complete]: { border: "border-green-500", label: "Complete", color: "text-green-600" },
  [EventType.Error]: { border: "border-red-500", label: "Error", color: "text-red-600" },
  [EventType.SimulationUpdated]: { border: "border-amber-400", label: "Sim", color: "text-amber-600" },
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
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col h-full shadow-sm">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <span className="text-gray-800 font-semibold text-sm">Event Feed</span>
        <span className="text-xs text-gray-400">{events.length} events</span>
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
                <span className="text-gray-400 mr-2">{formatTime(e.timestamp)}</span>
                <span className={`${style.color} mr-1 font-medium`}>{style.label}</span>
                <span className="text-gray-600">{eventSummary(e)}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
        {events.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-400">
            Waiting for events...
          </div>
        )}
      </div>
    </div>
  );
}
