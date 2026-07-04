import { useEffect, useRef, useState } from "react";
import { MatchInfo, matchApi } from "@/lib/matchApi";
import { SovereignState } from "@/lib/api";

type PresenceEvent = { type: "presence"; player_id: string; role: string; connected: boolean };
type StateEvent = { type: "state"; match: MatchInfo; state: SovereignState };
type SocketEvent = PresenceEvent | StateEvent;

export function useMatchSocket(matchId: string | null, token: string | null) {
  const [state, setState] = useState<SovereignState | null>(null);
  const [match, setMatch] = useState<MatchInfo | null>(null);
  const [connected, setConnected] = useState(false);
  const [opponentOnline, setOpponentOnline] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!matchId || !token) return;

    const socket = new WebSocket(matchApi.wsUrl(matchId, token));
    socketRef.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);

    socket.onmessage = (event) => {
      if (event.data === "pong") return;
      try {
        const parsed: SocketEvent = JSON.parse(event.data);
        if (parsed.type === "state") {
          setState(parsed.state);
          setMatch(parsed.match);
        } else if (parsed.type === "presence") {
          setOpponentOnline(parsed.connected);
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    // Heartbeat so idle connections aren't reaped by proxies/load balancers.
    const heartbeat = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send("ping");
    }, 25_000);

    return () => {
      clearInterval(heartbeat);
      socket.close();
      socketRef.current = null;
    };
  }, [matchId, token]);

  return { state, match, connected, opponentOnline, setState };
}
