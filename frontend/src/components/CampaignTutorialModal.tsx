"use client";

/**
 * CampaignTutorialModal — "How the Multi-City Campaign Works".
 * Same shape as TutorialModal.tsx (the single-city tutorial), but covers
 * the Campaign-only mechanics: opposite roles per city, the Black Money
 * Pipeline, staggered election phases, the Command Center UI, and
 * Asymmetric Retaliation. Opens automatically the first time a player
 * reaches /campaign (tracked via localStorage), and can be reopened any
 * time from the "How This Works" button in CommandCenter's sidebar.
 */

import { useState, type ReactNode } from "react";
import {
  Map,
  Banknote,
  CalendarClock,
  LayoutDashboard,
  Siren,
  PartyPopper,
  X,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export const CAMPAIGN_TUTORIAL_SEEN_KEY = "prajatantra.campaign_tutorial_seen.v1";

type Step = {
  icon: ReactNode;
  title: string;
  hindi: string;
  body: ReactNode;
};

const STEPS: Step[] = [
  {
    icon: <Map className="h-6 w-6" />,
    title: "One Campaign, Many Cities",
    hindi: "एक अभियान, कई शहर",
    body: (
      <>
        <p>
          A Campaign links 3–5 cities under the same two players — but unlike a normal match, your role
          <b> flips from city to city</b>. If you&apos;re <b>Incumbent</b> in Bengaluru, you&apos;re automatically{" "}
          <b>Opposition</b> in Mumbai, Incumbent again in Chennai, and so on.
        </p>
        <p className="mt-2">
          That&apos;s the whole point: you always have a city to defend and a city to attack, at the same time.
        </p>
      </>
    ),
  },
  {
    icon: <Banknote className="h-6 w-6" />,
    title: "The Black Money Pipeline",
    hindi: "काला धन पाइपलाइन",
    body: (
      <>
        <p>
          As Incumbent, <b>Commission a Project</b> with a siphon % — same as a normal build, except the skimmed
          cut (minus a 5% laundering fee) now lands in your <b>Private Offshore Account</b> instead of vanishing.
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            Spend that account with <b>Fund Riots/Strikes</b> in a city where you&apos;re Opposition — it buys
            Influence Points and quietly hurts that city&apos;s trust and unrest.
          </li>
          <li>
            Your rival can <b>Expose Offshore Laundering</b> in the source city (only if they&apos;re Opposition
            there) — it costs you trust, freezes your account, and instantly dries up funding anywhere it was
            active.
          </li>
        </ul>
      </>
    ),
  },
  {
    icon: <CalendarClock className="h-6 w-6" />,
    title: "Staggered Election Phases",
    hindi: "चरणबद्ध चुनाव",
    body: (
      <>
        <p>
          Cities don&apos;t all vote at once. City 1 votes alone in Phase 1; the rest split across later phases —
          just like real staggered general elections. A city only opens for voting once its phase has started.
        </p>
        <p className="mt-2">
          Win a city, and whoever won gets a <b>Momentum Buff (+10% base Trust)</b> automatically applied to their
          races in the <i>next</i> phase&apos;s cities. A strong Phase 1 result can snowball — or force a losing
          player to abandon governing one city just to go all-in defending another.
        </p>
      </>
    ),
  },
  {
    icon: <LayoutDashboard className="h-6 w-6" />,
    title: "The Command Center",
    hindi: "नियंत्रण कक्ष",
    body: (
      <>
        <p>
          The left sidebar is your <b>Global Map</b> — every city, colour-coded green (you&apos;re Incumbent) or
          red (you&apos;re Opposition), with warning icons like <b>⚠️ Strike</b> or <b>🚨 Audit in Progress</b>.
        </p>
        <p className="mt-2">
          Click a city to instantly swap the dashboard to its War Room. Turn on <b>Split-Screen Mode</b> to watch
          one city&apos;s live election counting while you act in another.
        </p>
      </>
    ),
  },
  {
    icon: <Siren className="h-6 w-6" />,
    title: "Asymmetric Retaliation",
    hindi: "असममित प्रतिशोध",
    body: (
      <>
        <p>
          From any city where you&apos;re Incumbent, play <b>Arrest Opposition Leaders</b> to misuse state
          machinery: it slashes your rival&apos;s Influence Points by 60% in <b>every</b> city they hold a seat in
          — for 5 minutes.
        </p>
        <p className="mt-2 text-[11px]" style={{ color: "var(--pt-muted)" }}>
          Mutually assured destruction: both of you hold power somewhere, so both of you can abuse it. There&apos;s
          no cooldown-free escape — only whether it&apos;s worth the trust hit.
        </p>
      </>
    ),
  },
];

export default function CampaignTutorialModal({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const isFirst = step === 0;
  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  function finish() {
    try {
      window.localStorage.setItem(CAMPAIGN_TUTORIAL_SEEN_KEY, "1");
    } catch {
      // ignore storage errors (private browsing etc.)
    }
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.72)" }}
      role="dialog"
      aria-modal="true"
      aria-label="How the multi-city campaign works"
    >
      <div
        className="flex max-h-[85vh] w-full max-w-lg flex-col"
        style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-saffron)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--pt-line)" }}>
          <div className="flex items-center gap-2" style={{ color: "var(--pt-saffron)" }}>
            {current.icon}
            <div>
              <div className="text-sm font-black uppercase" style={{ color: "var(--pt-white)" }}>
                {current.title}
              </div>
              <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
                {current.hindi}
              </div>
            </div>
          </div>
          <button type="button" onClick={finish} aria-label="Close tutorial" className="p-1" style={{ color: "var(--pt-muted)" }}>
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-4 text-sm" style={{ color: "var(--pt-white)" }}>
          {current.body}
        </div>

        {/* Progress dots */}
        <div className="flex items-center justify-center gap-1.5 pb-2">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: i === step ? "var(--pt-saffron)" : "var(--pt-line)" }}
            />
          ))}
        </div>

        {/* Footer nav */}
        <div className="flex items-center justify-between gap-2 px-4 py-3" style={{ borderTop: "1px solid var(--pt-line)" }}>
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={isFirst}
            className="flex items-center gap-1 px-3 py-2 text-xs font-bold uppercase disabled:opacity-30"
            style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
          >
            <ChevronLeft className="h-4 w-4" /> Peeche
          </button>
          <span className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
            {step + 1} / {STEPS.length}
          </span>
          {isLast ? (
            <button
              type="button"
              onClick={finish}
              className="flex items-center gap-1 px-3 py-2 text-xs font-black uppercase"
              style={{ background: "var(--pt-saffron)", color: "#fff" }}
            >
              <PartyPopper className="h-4 w-4" /> Abhiyaan Shuru Karein
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
              className="flex items-center gap-1 px-3 py-2 text-xs font-black uppercase"
              style={{ background: "var(--pt-saffron)", color: "#fff" }}
            >
              Aage <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
