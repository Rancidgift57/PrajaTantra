"""
Tactical Cards — the "Midnight Card" deck
==========================================
A rotating, cooldown-gated deck of real-time abilities for each seat.
Cooldowns are enforced per-match by cooldown_store (see cooldown_store.py),
so a card going on cooldown in one match never affects another. Effects
are applied by SovereignEngine.play_card() — this module only owns the
catalog (names, flavour, cooldowns), not the game-state mutation.
"""

from app.schemas.prajatantra import PlayerRole, TacticalCard

CARD_CATALOG: list[TacticalCard] = [
    TacticalCard(
        id="SECTION_144",
        name="Section 144",
        hindi="धारा 144",
        role="Incumbent",
        cooldown_seconds=240,
        description="Bans strikes against one target infrastructure block for 3 minutes.",
    ),
    TacticalCard(
        id="MEDIA_DISTRACTION",
        name="Media Distraction",
        hindi="मीडिया भटकाव",
        role="Incumbent",
        cooldown_seconds=300,
        description="Halves the trust damage of the NEXT leaked audit against you (one-shot).",
    ),
    TacticalCard(
        id="RTI_STING",
        name="RTI Sting",
        hindi="आरटीआई स्टिंग",
        role="Opposition",
        cooldown_seconds=240,
        description="Freezes a target block's revenue for 90 seconds and claws back one tick's worth immediately.",
    ),
    TacticalCard(
        id="TOOLDOWN",
        name="Tooldown",
        hindi="टूलडाउन",
        role="Opposition",
        cooldown_seconds=200,
        description="Halts a target block instantly, spiking citywide worker unrest.",
    ),
]

_CATALOG_BY_ID: dict[str, TacticalCard] = {c.id: c for c in CARD_CATALOG}


def get_card(card_id: str) -> TacticalCard | None:
    return _CATALOG_BY_ID.get(card_id)


def cards_for_role(role: PlayerRole) -> list[TacticalCard]:
    return [c for c in CARD_CATALOG if c.role == role]
