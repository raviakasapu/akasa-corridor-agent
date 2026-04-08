import type { AgentEvent } from "../types";

type MessageHandler = (event: AgentEvent) => void;

interface Connection {
  ws: WebSocket | null;
  handlers: Set<MessageHandler>;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
}

const conn: Connection = {
  ws: null,
  handlers: new Set(),
  reconnectTimer: null,
};

let isConnecting = false;

function getWsUrl(): string {
  const loc = window.location;
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}/ws/agent`;
}

export function connect(): Promise<WebSocket> {
  if (conn.ws?.readyState === WebSocket.OPEN) {
    return Promise.resolve(conn.ws);
  }

  if (isConnecting && conn.ws) {
    return new Promise((resolve, reject) => {
      const check = () => {
        if (conn.ws?.readyState === WebSocket.OPEN) resolve(conn.ws!);
        else if (!conn.ws || conn.ws.readyState > WebSocket.OPEN) reject();
        else setTimeout(check, 50);
      };
      check();
    });
  }

  if (conn.reconnectTimer) {
    clearTimeout(conn.reconnectTimer);
    conn.reconnectTimer = null;
  }

  conn.ws?.close();

  isConnecting = true;
  const url = getWsUrl();
  conn.ws = new WebSocket(url);

  return new Promise((resolve, reject) => {
    const onOpen = () => {
      isConnecting = false;
      conn.ws!.removeEventListener("open", onOpen);
      conn.ws!.removeEventListener("error", onErr);
      resolve(conn.ws!);
    };
    const onErr = () => {
      isConnecting = false;
      conn.ws!.removeEventListener("open", onOpen);
      conn.ws!.removeEventListener("error", onErr);
      reject(new Error("WebSocket connection failed"));
    };

    conn.ws!.addEventListener("open", onOpen);
    conn.ws!.addEventListener("error", onErr);

    conn.ws!.onmessage = (e) => {
      try {
        const parsed: AgentEvent = JSON.parse(e.data);
        conn.handlers.forEach((h) => h(parsed));
      } catch {
        // ignore malformed messages
      }
    };

    conn.ws!.onclose = () => {
      isConnecting = false;
      conn.reconnectTimer = setTimeout(() => {
        connect().catch(() => {});
      }, 3000);
    };
  });
}

export function disconnect() {
  if (conn.reconnectTimer) {
    clearTimeout(conn.reconnectTimer);
    conn.reconnectTimer = null;
  }
  conn.ws?.close(1000);
  conn.ws = null;
}

export function send(msg: Record<string, unknown>) {
  if (conn.ws?.readyState === WebSocket.OPEN) {
    conn.ws.send(JSON.stringify(msg));
  }
}

export function addHandler(h: MessageHandler): () => void {
  conn.handlers.add(h);
  return () => conn.handlers.delete(h);
}

export function isOpen(): boolean {
  return conn.ws?.readyState === WebSocket.OPEN;
}
