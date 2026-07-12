import { useEffect, useRef, useState } from "react";
import { CoalitionMatchInfo, coalitionApi } from "@/lib/coalitionApi";

type CoalitionStateEvent = { type: "coalition_state"; match: CoalitionMatchInfo };

export function useCoalitionSocket(matchId: string | null, token: string | null) {
  const [match, setMatch] = useState<CoalitionMatchInfo | null>(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!matchId || !token) return;

    const socket = new WebSocket(coalitionApi.wsUrl(matchId, token));
    socketRef.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);

    socket.onmessage = (event) => {
      if (event.data === "pong") return;
      try {
        const parsed: CoalitionStateEvent = JSON.parse(event.data);
        if (parsed.type === "coalition_state") setMatch(parsed.match);
      } catch {
        /* ignore malformed frames */
      }
    };

    const heartbeat = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send("ping");
    }, 25_000);

    return () => {
      clearInterval(heartbeat);
      socket.close();
      socketRef.current = null;
    };
  }, [matchId, token]);

  return { match, connected, setMatch };
}
