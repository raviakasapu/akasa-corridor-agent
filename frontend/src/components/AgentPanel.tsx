import { StatusBadge } from "./StatusBadge";
import { formatDuration, truncate } from "../utils/formatters";
import type { Agent } from "../types";
import { Cpu, Wrench, Clock, MessageSquare } from "lucide-react";

export function AgentPanel({ agent }: { agent: Agent }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-blue-600" />
          <span className="font-semibold text-gray-800 text-sm">{agent.name}</span>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      {agent.thinking && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <p className="text-purple-700 text-xs">{truncate(agent.thinking, 200)}</p>
        </div>
      )}

      {agent.content && (
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-1 mb-1">
            <MessageSquare className="w-3 h-3 text-gray-400" />
            <span className="text-xs text-gray-400">Response</span>
          </div>
          <p className="text-gray-700 text-sm whitespace-pre-wrap">
            {truncate(agent.content, 500)}
          </p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-blue-50 rounded-lg p-2">
          <Wrench className="w-3 h-3 text-blue-600 mx-auto mb-1" />
          <p className="text-gray-800 text-sm font-bold">{agent.totalToolCalls}</p>
          <p className="text-gray-400 text-xs">Tools</p>
        </div>
        <div className="bg-amber-50 rounded-lg p-2">
          <Clock className="w-3 h-3 text-amber-600 mx-auto mb-1" />
          <p className="text-gray-800 text-sm font-bold">
            {agent.durationS > 0 ? formatDuration(agent.durationS) : "-"}
          </p>
          <p className="text-gray-400 text-xs">Duration</p>
        </div>
        <div className="bg-purple-50 rounded-lg p-2">
          <Cpu className="w-3 h-3 text-purple-600 mx-auto mb-1" />
          <p className="text-gray-800 text-sm font-bold">{agent.iterations}</p>
          <p className="text-gray-400 text-xs">Iters</p>
        </div>
      </div>

      {agent.toolResults.length > 0 && (
        <div>
          <p className="text-xs text-gray-400 mb-1">Recent Tools</p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {agent.toolResults.slice(-5).map((tr, i) => (
              <div
                key={i}
                className={`text-xs px-2 py-1 rounded ${
                  tr.success
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "bg-red-50 text-red-700 border border-red-200"
                }`}
              >
                <span className="font-mono">{tr.tool}</span>
                {tr.summary && (
                  <span className="text-gray-400 ml-1">
                    {truncate(tr.summary, 60)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
