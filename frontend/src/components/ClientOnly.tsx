"use client";

/**
 * ClientOnly
 * ----------
 * Renders children ONLY after the component mounts on the client.
 * On the server (and during SSR), renders null.
 *
 * Why this fixes the removeChild crash:
 * --------------------------------------
 * React 19 crashes with "Failed to execute 'removeChild'" when browser
 * extensions (Google Translate, Grammarly, LastPass, etc.) inject extra
 * DOM nodes before React hydrates the SSR-rendered HTML. React expects
 * the DOM to exactly match what the server sent, but finds extra nodes,
 * then fails trying to remove them.
 *
 * By rendering null on the server, we send an empty shell. The client
 * then does a FRESH render with no prior DOM to reconcile against, so
 * extensions can do whatever they want without triggering the crash.
 */

import { useEffect, useState, type ReactNode } from "react";

export default function ClientOnly({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0C0F14",
          color: "#FF6B00",
          fontFamily: "Arial, sans-serif",
          fontSize: "0.9rem",
          letterSpacing: "0.1em",
          flexDirection: "column",
          gap: "1rem",
        }}
      >
        {/* Ashoka chakra ASCII spinner while page mounts */}
        <div style={{ fontSize: "2rem" }}>🇮🇳</div>
        <div>PrajaTantra — Loktantra Simulator</div>
        <div style={{ color: "#8A8070", fontSize: "0.75rem" }}>लोड हो रहा है…</div>
      </div>
    );
  }

  return <>{children}</>;
}