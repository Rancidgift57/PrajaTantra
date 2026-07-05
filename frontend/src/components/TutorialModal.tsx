"use client";

/**
 * TutorialModal — a short, multi-step "How to Play" walkthrough.
 * Opens automatically the first time a player reaches the Dashboard
 * (tracked via localStorage), and can be reopened any time from the
 * header's "Tutorial" button.
 */

import { useState, type ReactNode } from "react";
import {
  Landmark, Vote, Building2, ShieldAlert, Gavel, Handshake,
  X, ChevronLeft, ChevronRight, PartyPopper,
} from "lucide-react";

export const TUTORIAL_SEEN_KEY = "prajatantra.tutorial_seen.v1";

type Step = {
  icon: ReactNode;
  title: string;
  hindi: string;
  body: ReactNode;
};

const STEPS: Step[] = [
  {
    icon: <Landmark className="h-6 w-6" />,
    title: "Two Seats, One City",
    hindi: "एक शहर, दो कुर्सियाँ",
    body: (
      <>
        <p>PrajaTantra is played head-to-head, one seat each:</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li><b>Incumbent</b> — governs the city. Builds infrastructure, launches government schemes, manages the treasury, campaigns for re-election.</li>
          <li><b>Opposition</b> — investigates the Incumbent. Audits the corruption graph, leaks scandals to the press, calls strikes, and tries to flip the next election.</li>
        </ul>
        <p className="mt-2">Create a match to become Incumbent and get a join code, or join with a code to become Opposition.</p>
      </>
    ),
  },
  {
    icon: <Building2 className="h-6 w-6" />,
    title: "Build the City",
    hindi: "शहर का निर्माण",
    body: (
      <>
        <p>The City Map is a zoned grid — every tile only accepts certain buildings:</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li><b>Industrial</b> buildings (Port, Factory) pay well but raise pollution and unrest.</li>
          <li><b>Social</b> buildings (Hospital, School, Waste Plant) cost upkeep but raise public trust — your best tool before an election.</li>
          <li><b>Strategic</b> buildings (Tech Park, Power Grid) are the balanced middle ground and boost national prestige.</li>
        </ul>
        <p className="mt-2">Government <b>Schemes</b> stack on top — time-limited policies with an upfront + per-cycle cost.</p>
      </>
    ),
  },
  {
    icon: <Gavel className="h-6 w-6" />,
    title: "The Corruption Graph",
    hindi: "भ्रष्टाचार ग्राफ",
    body: (
      <>
        <p>Every construction project lets the Incumbent set a <b>siphon %</b> — skimming public funds for personal gain. This quietly generates a real, explorable money-laundering graph: Mayor → Shell Company → Vendor → Project.</p>
        <p className="mt-2">As Opposition, run a <b>CAG Audit</b> to trace it. Deep enough, and you find the <b>smoking gun</b> — then <b>leak it to the press</b> to damage the Incumbent's trust right before an election.</p>
      </>
    ),
  },
  {
    icon: <Handshake className="h-6 w-6" />,
    title: "Grants, Duels & Strikes",
    hindi: "अनुदान, द्वंद्व और हड़ताल",
    body: (
      <>
        <ul className="list-disc space-y-1 pl-5">
          <li><b>Federal Grant</b> (Incumbent) — request funds from the national government; approval depends on your political alignment.</li>
          <li><b>Trade Duel</b> (Incumbent) — a head-to-head economic contest against a rival country for a temporary GDP buff.</li>
          <li><b>Strike</b> (Opposition) — spend Influence Points to shut down one of the Incumbent's buildings, hurting revenue and raising unrest.</li>
        </ul>
      </>
    ),
  },
  {
    icon: <Vote className="h-6 w-6" />,
    title: "Elections Every 3 Days",
    hindi: "हर 3 दिन में चुनाव",
    body: (
      <>
        <p>Write a <b>manifesto</b> and a <b>campaign speech</b>. The manifesto is scored on practicality — does it name a real funding mechanism? — and is also judged by an <b>AI model</b> for credibility (populist promises with no funding plan get penalized hard).</p>
        <p className="mt-2">Then counting runs live across <b>24 rounds</b> — postal ballots, then urban centres, then volatile swing zones — blending your campaign score with an anti-incumbency wave (voters get tired of the same face after too many terms).</p>
        <p className="mt-2 text-[11px]" style={{ color: "var(--pt-muted)" }}>
          Your <b>Consecutive Terms in Power</b> counter is fully automatic — it climbs by itself every time the Incumbent wins, and resets the moment they lose. You never set it directly.
        </p>
      </>
    ),
  },
  {
    icon: <ShieldAlert className="h-6 w-6" />,
    title: "Seats & Emergency Powers",
    hindi: "सीटें और आपातकाल",
    body: (
      <>
        <p>Results render as a hemicycle <b>seat map</b> — saffron for Incumbent, red for Opposition, grey for a small reserved Independents bloc.</p>
        <p className="mt-2">Cross an <b>80% seat supermajority</b> as Incumbent, and you can <b>Declare Emergency</b> — a dictatorship-style power letting Industrial buildings bypass Residential zoning entirely, at the cost of some public trust.</p>
      </>
    ),
  },
];

export default function TutorialModal({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const isFirst = step === 0;
  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  function finish() {
    try {
      window.localStorage.setItem(TUTORIAL_SEEN_KEY, "1");
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
      aria-label="How to play PrajaTantra"
    >
      <div
        className="flex max-h-[85vh] w-full max-w-lg flex-col"
        style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-saffron)" }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: "1px solid var(--pt-line)" }}
        >
          <div className="flex items-center gap-2" style={{ color: "var(--pt-saffron)" }}>
            {current.icon}
            <div>
              <div className="text-sm font-black uppercase" style={{ color: "var(--pt-white)" }}>
                {current.title}
              </div>
              <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>{current.hindi}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={finish}
            aria-label="Close tutorial"
            className="p-1"
            style={{ color: "var(--pt-muted)" }}
          >
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
        <div
          className="flex items-center justify-between gap-2 px-4 py-3"
          style={{ borderTop: "1px solid var(--pt-line)" }}
        >
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
              <PartyPopper className="h-4 w-4" /> Khel Shuru Karein
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
