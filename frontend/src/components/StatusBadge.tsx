import type { MissionStatus } from "../types";

const config: Record<
  MissionStatus | string,
  { label: string; color: string; bg: string; pulse: boolean }
> = {
  idle: { label: "Idle", color: "text-gray-400", bg: "bg-gray-500/10", pulse: false },
  connecting: { label: "Connecting", color: "text-yellow-400", bg: "bg-yellow-500/10", pulse: true },
  running: { label: "Running", color: "text-blue-400", bg: "bg-blue-500/10", pulse: true },
  complete: { label: "Complete", color: "text-green-400", bg: "bg-green-500/10", pulse: false },
  error: { label: "Error", color: "text-red-400", bg: "bg-red-500/10", pulse: false },
  thinking: { label: "Thinking", color: "text-purple-400", bg: "bg-purple-500/10", pulse: true },
  executing: { label: "Executing", color: "text-blue-400", bg: "bg-blue-500/10", pulse: true },
};

export function StatusBadge({ status }: { status: string }) {
  const c = config[status] || config.idle;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${c.bg} ${c.color}`}
    >
      {c.pulse && (
        <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
      )}
      {c.label}
    </span>
  );
}
