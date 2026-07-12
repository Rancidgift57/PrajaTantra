import { useEffect, useRef, useState } from "react";
import { MatchInfo, matchApi } from "@/lib/matchApi";
import { SovereignState } from "@/lib/api";

type PresenceEvent = { type: "presence"; player_id: string; role: string; connected: boolean };
type StateEvent = { type: "state"; match: MatchInfo; state: SovereignState };
type SocketEvent = PresenceEvent | StateEvent;

const RECONNECT_DELAYS_MS = [500, 1500, 3000, 6000, 10_000]; // capped backoff

export function useMatchSocket(matchId: string | null, token: string | null) {
  const [state, setState] = useState<SovereignState | null>(null);
  const [match, setMatch] = useState<MatchInfo | null>(null);
  const [connected, setConnected] = useState(false);
  const [opponentOnline, setOpponentOnline] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!matchId || !token) return;

    // `active` guards every callback below: if matchId/token change (or the
    // component unmounts) while a connect attempt or reconnect timer is in
    // flight, those stale closures become no-ops instead of mutating state
    // for a socket the effect has already moved on from. Without this,
    // fast prop changes can fire a `close()` on a socket that never
    // finished opening — the "WebSocket is closed before the connection is
    // established" warning — and can also race a state update against an
    // unmount, which is a common trigger for the React "removeChild" error.
    let active = true;
    let socket: WebSocket | null = null;
    let heartbeat: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    function connect() {
      if (!active) return;
      socket = new WebSocket(matchApi.wsUrl(matchId as string, token as string));
      socketRef.current = socket;

      socket.onopen = () => {
        if (!active) return;
        attempt = 0;
        setConnected(true);
      };

      socket.onclose = () => {
        if (!active) return;
        setConnected(false);
        // Bounded auto-reconnect — smooths over a backend cold start
        // (e.g. Render free tier waking up) instead of leaving the player
        // stuck on a dead connection with no feedback.
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

  return { state, match, connected, opponentOnline, setState };
}
