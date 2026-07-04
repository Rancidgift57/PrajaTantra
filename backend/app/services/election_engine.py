import re

from app.schemas.prajatantra import ElectionScoreRequest, ElectionScoreResponse
from app.services.incumbency_engine import calculate_incumbency_wave, wave_label
from app.services.manifesto_ai import score_manifesto_with_ai


class ElectionEngine:
    attack_terms = {"corrupt", "failed", "scam", "leak", "waste", "lie", "incompetent", "crony"}
    vision_terms = {"build", "fund", "jobs", "health", "schools", "roads", "industry", "clean", "plan", "deliver"}
    cta_terms = {"vote", "join", "choose", "mandate", "together", "support"}

    def grade(self, payload: ElectionScoreRequest) -> ElectionScoreResponse:
        practicality, practicality_notes, ai_judging = self._practicality(payload)
        rhetoric, rhetoric_notes, rhetoric_breakdown = self._rhetoric(payload.speech_transcript)
        city_score = self._city_score(payload)

        trust = round((city_score * 0.38) + (practicality * 0.34) + (rhetoric * 0.28))
        penalties = [*practicality_notes, *rhetoric_notes]

        # ── Incumbency Wave modifier ────────────────────────────────────────
        # The macro wave is computed from the city's live public_trust, the
        # number of exposed scams, and the configured consecutive terms.
        i_f = calculate_incumbency_wave(
            global_trust=float(payload.city_stats.public_trust),
            scams_exposed=payload.city_stats.corruption_leaks,
            consecutive_terms=payload.consecutive_terms,
        )
        # Scale the [-40, +40] wave into a [-20, +20] trust-score modifier
        # so it acts as a meaningful nudge without becoming the only signal.
        wave_modifier = round(i_f * 0.5)
        trust += wave_modifier

        wave = wave_label(i_f)
        if wave_modifier < 0:
            penalties.append(
                f"Incumbency Wave ({wave}): macro voter mood shaved {abs(wave_modifier)} trust points."
            )
        elif wave_modifier > 0:
            penalties.append(
                f"Incumbency Wave ({wave}): favourable governance mood added {wave_modifier} trust points."
            )
        # ───────────────────────────────────────────────────────────────────

        # Legacy per-leak drag still applies on top (stacks with wave)
        if payload.city_stats.corruption_leaks >= 2:
            leak_drag = min(payload.city_stats.corruption_leaks * 5, 20)
            trust -= leak_drag
            penalties.append("Leak drag: repeated corruption leaks reduced public trust.")

        trust = max(0, min(100, trust))
        return ElectionScoreResponse(
            practicality_score=practicality,
            rhetoric_score=rhetoric,
            city_performance_score=city_score,
            trust_score=trust,
            penalties=penalties,
            breakdown={
                "manifesto_word_count": len(payload.manifesto.split()),
                "speech_word_count": len(payload.speech_transcript.split()),
                "incumbency_factor": round(i_f, 2),
                "wave_label": wave,
                "wave_trust_modifier": wave_modifier,
                "manifesto_ai_score": ai_judging["score"],
                "manifesto_ai_source": ai_judging["source"],
                **rhetoric_breakdown,
            },
        )

    def _practicality(self, payload: ElectionScoreRequest) -> tuple[int, list[str], dict]:
        text = payload.manifesto.lower()
        notes: list[str] = []
        score = 55

        addressed = sum(1 for crisis in payload.crises if any(token in text for token in self._keywords(crisis)))
        score += addressed * 12
        if addressed < len(payload.crises):
            notes.append("Manifesto did not address every generated crisis.")

        expensive_promises = len(re.findall(r"\b(free|universal|guaranteed|mega|world-class|waive|subsidy)\b", text))
        estimated_burden = expensive_promises * 300_000
        if estimated_burden > payload.city_stats.treasury:
            score -= 28
            notes.append("Populist overreach: promises exceed available treasury.")
        elif expensive_promises:
            score -= expensive_promises * 3

        if re.search(r"\b(tax|tariff|grant|bond|ppp|public-private|phased|audit)\b", text):
            score += 10
        else:
            notes.append("No funding mechanism detected.")

        word_count = len(payload.manifesto.split())
        if word_count < 120:
            score -= 12
            notes.append("Manifesto is too thin for a 300-word policy phase.")
        elif 240 <= word_count <= 360:
            score += 6

        # AI manifesto judging (HuggingFace zero-shot, with an offline
        # heuristic fallback when no API token/network is available).
        ai_judging = score_manifesto_with_ai(payload.manifesto)
        score += round((ai_judging["score"] - 50) * 0.2)
        if ai_judging["source"] == "huggingface":
            notes.append(f"AI manifesto judge (HuggingFace): credibility score {ai_judging['score']}/100.")
        else:
            notes.append(f"AI manifesto judge unavailable — used offline heuristic ({ai_judging['score']}/100).")

        return max(0, min(100, score)), notes, ai_judging

    def _rhetoric(self, transcript: str) -> tuple[int, list[str], dict[str, int | str | float]]:
        words = re.findall(r"[a-zA-Z']+", transcript.lower())
        notes: list[str] = []
        if not words:
            return 0, ["No campaign speech transcript was provided."], {
                "vision_share": 0,
                "attack_share": 0,
                "call_to_action_share": 0,
            }

        vision_hits = sum(1 for word in words if word in self.vision_terms)
        attack_hits = sum(1 for word in words if word in self.attack_terms)
        cta_hits = sum(1 for word in words if word in self.cta_terms)
        total_hits = max(1, vision_hits + attack_hits + cta_hits)

        vision_share = vision_hits / total_hits
        attack_share = attack_hits / total_hits
        cta_share = cta_hits / total_hits

        balance = (
            60 * (1 - min(abs(0.60 - vision_share) / 0.60, 1))
            + 30 * (1 - min(abs(0.30 - attack_share) / 0.30, 1))
            + 10 * (1 - min(abs(0.10 - cta_share) / 0.10, 1))
        )
        score = round(balance)

        if attack_share > 0.65:
            score -= 25
            notes.append("Demagogue penalty: speech is dominated by attacks.")
        if attack_share < 0.05:
            score -= 14
            notes.append("Weak Leader penalty: speech avoids opponent accountability.")
        if len(words) < 220:
            score -= 10
            notes.append("Speech is short for a 3-minute campaign window.")

        return max(0, min(100, score)), notes, {
            "vision_share": round(vision_share, 2),
            "attack_share": round(attack_share, 2),
            "call_to_action_share": round(cta_share, 2),
        }

    def _city_score(self, payload: ElectionScoreRequest) -> int:
        stats = payload.city_stats
        gdp_component = min(stats.gdp / 12_000, 35)
        health_component = stats.health * 0.35
        employment_component = (100 - stats.unemployment) * 0.2
        treasury_component = min(stats.treasury / 80_000, 10)
        return round(max(0, min(100, gdp_component + health_component + employment_component + treasury_component)))

    def _keywords(self, crisis: str) -> set[str]:
        return {word for word in re.findall(r"[a-zA-Z]+", crisis.lower()) if len(word) > 3}


election_engine = ElectionEngine()