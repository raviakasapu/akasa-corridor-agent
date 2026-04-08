import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, AlertTriangle, AlertCircle, Info, Cpu, Wind, Radio } from "lucide-react";
import type { EdgeAlert, EdgeTelemetry } from "../types";

function GaugeBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-[10px]">
        <span className="text-gray-500">{label}</span>
        <span className="text-gray-700 font-medium">{value.toFixed(1)}</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function AlertItem({ alert }: { alert: EdgeAlert }) {
  const severityStyles = {
    INFO: { bg: "bg-blue-50", border: "border-blue-200", icon: <Info className="w-3 h-3 text-blue-500" /> },
    WARNING: { bg: "bg-amber-50", border: "border-amber-200", icon: <AlertTriangle className="w-3 h-3 text-amber-500" /> },
    CRITICAL: { bg: "bg-red-50", border: "border-red-300", icon: <AlertCircle className="w-3 h-3 text-red-500" /> },
  };
  const style = severityStyles[alert.severity] || severityStyles.INFO;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className={`${style.bg} ${style.border} border rounded-lg px-2 py-1.5 text-[11px]`}
    >
      <div className="flex items-center gap-1.5">
        {style.icon}
        <span className="font-medium text-gray-700">{alert.alertType.replace(/_/g, " ")}</span>
        {alert.acknowledged && <span className="text-green-600 ml-auto text-[9px] font-medium">ACK</span>}
        {!alert.acknowledged && alert.severity === "CRITICAL" && (
          <span className="text-red-600 ml-auto text-[9px] font-medium animate-pulse">PENDING</span>
        )}
      </div>
      <p className="text-gray-500 mt-0.5">{alert.message}</p>
    </motion.div>
  );
}

interface Props {
  alerts: EdgeAlert[];
  telemetry: EdgeTelemetry | null;
}

export function EdgePanel({ alerts, telemetry }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [alerts]);

  const pending = alerts.filter((a) => !a.acknowledged);
  const hasCritical = pending.some((a) => a.severity === "CRITICAL");

  return (
    <div className={`bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col h-full ${hasCritical ? "border-red-300" : "border-gray-200"}`}>
      {/* Header */}
      <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-cyan-600" />
          <span className="text-gray-800 font-semibold text-sm">Edge Computer</span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          {telemetry && (
            <span className="text-green-600 font-medium flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
              MONITORING
            </span>
          )}
          {pending.length > 0 && (
            <span className={`font-medium px-1.5 py-0.5 rounded-full ${hasCritical ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>
              {pending.length} pending
            </span>
          )}
        </div>
      </div>

      {/* Telemetry Gauges */}
      {telemetry && (
        <div className="px-4 py-2 border-b border-gray-100 space-y-1.5">
          <div className="grid grid-cols-3 gap-3 text-center text-[10px] mb-1">
            <div>
              <p className="text-gray-400">Match Rate</p>
              <p className={`font-bold text-sm ${telemetry.blockMatchRate >= 0.9 ? "text-green-600" : telemetry.blockMatchRate >= 0.7 ? "text-amber-600" : "text-red-600"}`}>
                {(telemetry.blockMatchRate * 100).toFixed(0)}%
              </p>
            </div>
            <div>
              <p className="text-gray-400">Conformance</p>
              <p className={`font-bold text-sm ${telemetry.conformanceScore >= 0.9 ? "text-green-600" : telemetry.conformanceScore >= 0.8 ? "text-amber-600" : "text-red-600"}`}>
                {(telemetry.conformanceScore * 100).toFixed(0)}%
              </p>
            </div>
            <div>
              <p className="text-gray-400">Progress</p>
              <p className="text-blue-600 font-bold text-sm">{telemetry.progressPercent.toFixed(0)}%</p>
            </div>
          </div>
          <GaugeBar label="Avg Deviation" value={telemetry.avgDeviationM} max={100} color="bg-amber-400" />
          <GaugeBar label="Max Deviation" value={telemetry.maxDeviationM} max={150} color="bg-red-400" />
          <div className="flex gap-3 text-[10px] text-gray-400 pt-0.5">
            <span className="flex items-center gap-0.5"><Wind className="w-3 h-3" /> {telemetry.avgWindSpeed.toFixed(1)} m/s</span>
            <span className="flex items-center gap-0.5"><Radio className="w-3 h-3" /> {telemetry.elapsedSeconds.toFixed(0)}s</span>
          </div>
        </div>
      )}

      {/* Alert Feed */}
      <div className="px-3 py-2 flex items-center justify-between border-b border-gray-100">
        <span className="text-xs text-gray-500 font-medium">Alerts</span>
        <span className="text-[10px] text-gray-400">{alerts.length} total</span>
      </div>
      <div ref={ref} className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0">
        <AnimatePresence initial={false}>
          {alerts.slice(-20).map((a) => (
            <AlertItem key={a.alertId} alert={a} />
          ))}
        </AnimatePresence>
        {alerts.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-400 text-xs">
            No alerts yet
          </div>
        )}
      </div>
    </div>
  );
}
