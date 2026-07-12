import { useEffect, useRef, useState } from "react";
import { CoalitionMatchInfo, coalitionApi } from "@/lib/coalitionApi";

type CoalitionStateEvent = { type: "coalition_state"; match: CoalitionMatchInfo };

const RECONNECT_DELAYS_MS = [500, 1500, 3000, 6000, 10_000]; // capped backoff

export function useCoalitionSocket(matchId: string | null, token: string | null) {
  const [match, setMatch] = useState<CoalitionMatchInfo | null>(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!matchId || !token) return;

    // Same `active` guard pattern as useMatchSocket.ts — prevents a stale
    // connect/reconnect attempt from mutating state (or closing a socket
    // mid-handshake) after matchId/token change or the component unmounts.
    let active = true;
    let socket: WebSocket | null = null;
    let heartbeat: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    function connect() {
      if (!active) return;
      socket = new WebSocket(coalitionApi.wsUrl(matchId as string, token as string));
      socketRef.current = socket;

      socket.onopen = () => {
        if (!active) return;
        attempt = 0;
        setConnected(true);
      };

      socket.onclose = () => {
        if (!active) return;
        setConnected(false);
        if (attempt < RECONNECT_DELAYS_MS.length) {
          const delay = RECONNECT_DELAYS_MS[attempt];
          attempt += 1;
          reconnectTimer = setTimeout(connect, delay);
        }
      };

      socket.onerror = () => {
        if (!active) return;
        setConnected(false);
      };

      socket.onmessage = (event) => {
        if (!active) return;
        if (event.data === "pong") return;
        try {
          const parsed: CoalitionStateEvent = JSON.parse(event.data);
          if (parsed.type === "coalition_state") setMatch(parsed.match);
        } catch {
          /* ignore malformed frames */
        }
      };

      heartbeat = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) socket.send("ping");
      }, 25_000);
    }

    connect();

    return () => {
      active = false;
      if (heartbeat) clearInterval(heartbeat);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) {
        socket.onopen = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        socket.close();
      }
      socketRef.current = null;
    };
  }, [matchId, token]);

  return { match, connected, setMatch };
}
