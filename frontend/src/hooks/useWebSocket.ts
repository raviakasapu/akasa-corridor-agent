import { useEffect, useRef } from "react";
import { connect, disconnect, addHandler, isOpen } from "../utils/websocket";
import { useMissionStore } from "../store/missionStore";
import type { AgentEvent } from "../types";

export function useWebSocket(onMessage?: (event: AgentEvent) => void) {
  const setConnected = useMissionStore((s) => s.setConnected);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    const remove = addHandler((event) => {
      handlerRef.current?.(event);
    });

    connect()
      .then(() => setConnected(true))
      .catch(() => setConnected(false));

    // Poll connection state
    const interval = setInterval(() => {
      setConnected(isOpen());
    }, 2000);

    return () => {
      remove();
      clearInterval(interval);
    };
  }, [setConnected]);
}
