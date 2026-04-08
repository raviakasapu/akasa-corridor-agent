import { StatusBadge } from "./StatusBadge";
import { formatDuration, truncate } from "../utils/formatters";
import type { Agent } from "../types";
import { Cpu, Wrench, Clock, MessageSquare } from "lucide-react";

export function AgentPanel({ agent }: { agent: Agent }) {
  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-800 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-blue-400" />
          <span className="font-medium text-white text-sm">{agent.name}</span>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      {agent.thinking && (
        <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-3">
          <p className="text-purple-300 text-xs">{truncate(agent.thinking, 200)}</p>
        </div>
      )}

      {agent.content && (
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="flex items-center gap-1 mb-1">
            <MessageSquare className="w-3 h-3 text-gray-400" />
            <span className="text-xs text-gray-400">Response</span>
          </div>
          <p className="text-gray-200 text-sm whitespace-pre-wrap">
            {truncate(agent.content, 500)}
          </p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-gray-800/40 rounded-lg p-2">
          <Wrench className="w-3 h-3 text-blue-400 mx-auto mb-1" />
          <p className="text-white text-sm font-bold">{agent.totalToolCalls}</p>
          <p className="text-gray-500 text-xs">Tools</p>
        </div>
        <div className="bg-gray-800/40 rounded-lg p-2">
          <Clock className="w-3 h-3 text-yellow-400 mx-auto mb-1" />
          <p className="text-white text-sm font-bold">
            {agent.durationS > 0 ? formatDuration(agent.durationS) : "-"}
          </p>
          <p className="text-gray-500 text-xs">Duration</p>
        </div>
        <div className="bg-gray-800/40 rounded-lg p-2">
          <Cpu className="w-3 h-3 text-purple-400 mx-auto mb-1" />
          <p className="text-white text-sm font-bold">{agent.iterations}</p>
          <p className="text-gray-500 text-xs">Iters</p>
        </div>
      </div>

      {agent.toolResults.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-1">Recent Tools</p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {agent.toolResults.slice(-5).map((tr, i) => (
              <div
                key={i}
                className={`text-xs px-2 py-1 rounded ${
                  tr.success ? "bg-green-500/10 text-green-300" : "bg-red-500/10 text-red-300"
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
