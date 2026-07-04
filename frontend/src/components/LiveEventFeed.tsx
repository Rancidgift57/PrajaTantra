"use client";

import { useEffect, useRef, useState } from "react";

type ToastItem = { id: number; text: string; ts: number };

/**
 * Diffs an incoming `headlines` array (already pushed to both players over
 * the match WebSocket as part of every state broadcast) and pops each new
 * entry in as a toast. Because it rides the existing broadcast, there is
 * zero extra backend work — the moment your opponent builds a factory,
 * launches a strike, or leaks an audit, you see it appear on your screen
 * within the same tick they act. That immediacy — "something just
 * happened, and it affects me" — is what turns a slow city-builder into
 * something you keep glancing back at.
 *
 * IDs come from a monotonically increasing counter (`nextId`), not
 * `Date.now()`. Actions that fire multiple rapid state updates (e.g.
 * Simulate Election makes two API calls back-to-back, and each match
 * action also arrives via both the REST response and the WebSocket
 * broadcast) can land within the same millisecond — Date.now()-based ids
 * would collide, giving two toasts the same React key, which breaks
 * reconciliation and crashes with "Failed to execute 'removeChild'".
 * A counter can never repeat.
 */
export default function LiveEventFeed({ headlines }: { headlines: string[] }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const seenCount = useRef(0);
  const nextId = useRef(0);
  const expandedRef = useRef(expanded);
  const mountedRef = useRef(true);

  // Keep a ref in sync so the setTimeout callbacks below always read the
  // *current* expanded state instead of the stale value captured when the
  // timer was scheduled.
  useEffect(() => {
    expandedRef.current = expanded;
  }, [expanded]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (headlines.length <= seenCount.current) {
      seenCount.current = headlines.length;
      return;
    }
    const fresh = headlines.slice(seenCount.current);
    seenCount.current = headlines.length;

    const newToasts: ToastItem[] = fresh.map((text) => ({
      id: nextId.current++,
      text,
      ts: Date.now(),
    }));
    setToasts((prev) => [...newToasts, ...prev].slice(0, 20));
    if (!expandedRef.current) setUnread((n) => n + newToasts.length);

    // Auto-dismiss each toast bubble after 6s (log stays visible if the
    // panel is expanded — checked live via the ref, not a stale closure).
    newToasts.forEach((t) => {
      setTimeout(() => {
        if (!mountedRef.current) return;
        setToasts((prev) => (expandedRef.current ? prev : prev.filter((x) => x.id !== t.id)));
      }, 6000);
    });
  }, [headlines]);

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex w-80 flex-col-reverse gap-2">
      {/* Floating toast bubbles */}
      {!expanded &&
        toasts.slice(0, 4).map((t) => (
          <div
            key={t.id}
            className="animate-[slideIn_0.25s_ease-out] px-3 py-2 text-xs leading-5 shadow-lg"
            style={{
              background: "var(--pt-panel)",
              border: "1px solid var(--pt-saffron)",
              color: "var(--pt-white)",
            }}
          >
            <span style={{ color: "var(--pt-saffron)" }}>⚡ LIVE </span>
            {t.text}
          </div>
        ))}

      {/* Toggle / expanded log */}
      <button
        type="button"
        onClick={() => {
          setExpanded((e) => !e);
          setUnread(0);
        }}
        className="relative flex items-center gap-2 self-end px-3 py-1.5 text-[10px] font-bold uppercase"
        style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
      >
        📡 Live Feed
        {unread > 0 && (
          <span
            className="flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[9px] font-black"
            style={{ background: "var(--pt-red)", color: "#fff" }}
          >
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {expanded && (
        <div
          className="max-h-64 overflow-auto p-2"
          style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-line)" }}
        >
          {toasts.length === 0 ? (
            <div className="p-2 text-[10px]" style={{ color: "var(--pt-muted)" }}>
              Koi live event nahi hua abhi tak.
            </div>
          ) : (
            toasts.map((t) => (
              <div
                key={t.id}
                className="px-2 py-1.5 text-[10px] leading-4"
                style={{ borderBottom: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
              >
                {t.text}
              </div>
            ))
          )}
        </div>
      )}

      <style jsx>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(24px); }
          to   { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}