import { motion } from "framer-motion";
import { Wrench, Check, X } from "lucide-react";
import { truncate } from "../utils/formatters";
import type { ToolCall, ToolResult } from "../types";

function ToolCallCard({ tc }: { tc: ToolCall }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-2 text-xs"
    >
      <div className="flex items-center gap-1 mb-1">
        <Wrench className="w-3 h-3 text-blue-400" />
        <span className="font-mono text-blue-300">{tc.tool}</span>
        <span className="text-gray-600 ml-auto">#{tc.toolIndex}</span>
      </div>
      <pre className="text-gray-400 overflow-x-auto">
        {truncate(JSON.stringify(tc.args, null, 1), 120)}
      </pre>
    </motion.div>
  );
}

function ToolResultCard({ tr }: { tr: ToolResult }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className={`border rounded-lg p-2 text-xs ${
        tr.success
          ? "bg-green-500/10 border-green-500/20"
          : "bg-red-500/10 border-red-500/20"
      }`}
    >
      <div className="flex items-center gap-1">
        {tr.success ? (
          <Check className="w-3 h-3 text-green-400" />
        ) : (
          <X className="w-3 h-3 text-red-400" />
        )}
        <span className="font-mono text-gray-300">{tr.tool}</span>
      </div>
      {tr.summary && (
        <p className="text-gray-400 mt-1">{truncate(tr.summary, 100)}</p>
      )}
    </motion.div>
  );
}

export function ToolExecutor({
  toolCalls,
  toolResults,
}: {
  toolCalls: ToolCall[];
  toolResults: ToolResult[];
}) {
  const recent = [...toolCalls.slice(-3), ...toolResults.slice(-3)];
  if (recent.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-500 font-medium">Tool Activity</p>
      {toolCalls.slice(-3).map((tc, i) => (
        <ToolCallCard key={`call-${i}`} tc={tc} />
      ))}
      {toolResults.slice(-3).map((tr, i) => (
        <ToolResultCard key={`result-${i}`} tr={tr} />
      ))}
    </div>
  );
}
