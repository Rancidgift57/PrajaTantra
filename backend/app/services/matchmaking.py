from app.schemas.prajatantra import MatchmakingRequest, MatchmakingResponse, PlayerMatchProfile


IDEOLOGY_DISTANCE = {
    ("Industrialist", "Green"): 42,
    ("Industrialist", "Socialist"): 35,
    ("Industrialist", "Nationalist"): 20,
    ("Industrialist", "Technocrat"): 18,
    ("Green", "Socialist"): 16,
    ("Green", "Nationalist"): 30,
    ("Green", "Technocrat"): 22,
    ("Socialist", "Nationalist"): 28,
    ("Socialist", "Technocrat"): 18,
    ("Nationalist", "Technocrat"): 12,
}


class MatchmakingEngine:
    def pair(self, payload: MatchmakingRequest) -> MatchmakingResponse:
        if not payload.candidates:
            return MatchmakingResponse(selected=None, friction_score=0, reason="No candidates are currently queued.")

        scored = [(self._score(payload.queued_player, candidate), candidate) for candidate in payload.candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        score, selected = scored[0]
        return MatchmakingResponse(
            selected=selected,
            friction_score=score,
            reason=(
                f"{selected.username} is close enough in Political MMR while creating a strong "
                f"{payload.queued_player.ideology} vs {selected.ideology} campaign contrast."
            ),
        )

    def _score(self, queued: PlayerMatchProfile, candidate: PlayerMatchProfile) -> int:
        mmr_gap = abs(queued.political_mmr - candidate.political_mmr)
        mmr_score = max(0, 38 - round(mmr_gap / 18))
        ideology_score = self._ideology_distance(queued.ideology, candidate.ideology)
        trust_gap_bonus = min(abs(queued.trust - candidate.trust), 20)
        gdp_gap_bonus = min(abs(queued.gdp_score - candidate.gdp_score), 12)
        return max(0, min(100, mmr_score + ideology_score + trust_gap_bonus + gdp_gap_bonus))

    def _ideology_distance(self, left: str, right: str) -> int:
        if left == right:
            return 4
        return IDEOLOGY_DISTANCE.get((left, right)) or IDEOLOGY_DISTANCE.get((right, left)) or 10


matchmaking_engine = MatchmakingEngine()

