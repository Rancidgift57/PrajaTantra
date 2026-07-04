"""
Manifesto AI Judge
==================
Scores a candidate's manifesto text for credibility using a zero-shot
classification model hosted on the HuggingFace Inference API. This score
feeds into ElectionEngine's practicality score, so how "real" a manifesto
sounds (funded plan vs. vague populist promise vs. corrupt/unfunded promise)
actually moves the trust score — and, downstream, the seat map.

Configuration
-------------
Set HUGGINGFACE_API_TOKEN (or HF_API_TOKEN) to enable live AI judging.
Optionally set HF_MANIFESTO_MODEL to override the default zero-shot model.

Without a token, no network access, or on any request failure, this module
falls back to a deterministic keyword heuristic — mirroring the same
"live service with in-memory/heuristic fallback" pattern used elsewhere in
this codebase (see corruption_graph's Neo4j fallback).
"""

import json
import os
import re
import urllib.error
import urllib.request

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/{model}"
DEFAULT_MODEL = os.getenv("HF_MANIFESTO_MODEL", "facebook/bart-large-mnli")
REQUEST_TIMEOUT_SECONDS = 6

CANDIDATE_LABELS = [
    "a credible, funded governance plan",
    "a vague populist promise",
    "a corrupt or fiscally reckless promise",
]

_FUNDING_TOKENS = re.compile(r"\b(tax|tariff|grant|bond|ppp|public-private|phased|audit|budget)\b", re.I)
_OVERREACH_TOKENS = re.compile(r"\b(free|universal|guaranteed|mega|world-class|waive|subsidy)\b", re.I)


def _heuristic_score(manifesto: str) -> dict:
    """Deterministic, offline keyword-based fallback."""
    text = manifesto.lower().strip()
    if not text:
        return {"score": 50.0, "source": "heuristic-fallback", "labels": {}}

    funded_hits = len(_FUNDING_TOKENS.findall(text))
    overreach_hits = len(_OVERREACH_TOKENS.findall(text))
    word_count = len(text.split())

    score = 50.0 + min(funded_hits * 6, 24) - min(overreach_hits * 4, 20)
    if word_count < 60:
        score -= 8
    score = max(0.0, min(100.0, score))

    return {"score": round(score, 1), "source": "heuristic-fallback", "labels": {}}


def score_manifesto_with_ai(manifesto: str) -> dict:
    """
    Returns {"score": 0-100, "source": "huggingface" | "heuristic-fallback", "labels": {...}}

    `score` blends toward 100 for a credible funded plan and toward 0 for
    vague/populist or corrupt/unfunded promises.
    """
    token = os.getenv("HUGGINGFACE_API_TOKEN") or os.getenv("HF_API_TOKEN")
    if not token or not manifesto.strip():
        return _heuristic_score(manifesto)

    try:
        body = json.dumps(
            {
                "inputs": manifesto[:1000],
                "parameters": {"candidate_labels": CANDIDATE_LABELS, "multi_label": True},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            HF_INFERENCE_URL.format(model=DEFAULT_MODEL),
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))

        labels = payload.get("labels", [])
        scores = payload.get("scores", [])
        if not labels or not scores:
            return _heuristic_score(manifesto)

        label_scores = dict(zip(labels, scores))
        credible = label_scores.get(CANDIDATE_LABELS[0], 0.0)
        vague = label_scores.get(CANDIDATE_LABELS[1], 0.0)
        corrupt = label_scores.get(CANDIDATE_LABELS[2], 0.0)

        score = 50.0 + (credible * 50.0) - (vague * 25.0) - (corrupt * 40.0)
        score = max(0.0, min(100.0, score))

        return {"score": round(score, 1), "source": "huggingface", "labels": {k: round(v, 3) for k, v in label_scores.items()}}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
        # No network in this environment, rate limit, model cold-start, malformed
        # response, etc. — degrade gracefully instead of failing the request.
        return _heuristic_score(manifesto)
