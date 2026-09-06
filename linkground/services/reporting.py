from __future__ import annotations

from typing import Any


def build_research_block(
    *,
    evidence_mode: str,
    discovery_weight: float,
    groundedness_score: float,
    authority_multiplier: float,
    trust_index: float,
    caller_url_count: int,
    discovered_url_count: int,
) -> dict[str, Any]:
    inflation = round(max(0.0, trust_index - groundedness_score), 3)

    flags: list[str] = []
    if evidence_mode in {"discovered", "mixed"}:
        flags.append("discovery")
    if discovery_weight < 1.0:
        flags.append(f"discount:{discovery_weight}")
    if authority_multiplier >= 1.1 and groundedness_score <= 0.4:
        flags.append("high_prestige_low_support")
    if caller_url_count == 0:
        flags.append("no_citations")

    if caller_url_count > 0 and discovered_url_count == 0:
        source = "cited"
    elif caller_url_count == 0 and discovered_url_count > 0:
        source = "discovered"
    elif caller_url_count > 0 and discovered_url_count > 0:
        source = "mixed"
    else:
        source = "none"

    return {
        "support": groundedness_score,
        "prestige": authority_multiplier,
        "inflation": inflation,
        "source": source,
        "flags": flags,
    }
