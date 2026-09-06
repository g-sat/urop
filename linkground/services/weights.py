from __future__ import annotations
from linkground.config import DISCOVERY_SCORE_FACTOR

def evidence_origin_weight(evidence_mode: str, *, caller_url_count: int, discovered_url_count: int, discovery_factor: float | None=None) -> float:
    factor = DISCOVERY_SCORE_FACTOR if discovery_factor is None else discovery_factor
    factor = min(1.0, max(0.05, float(factor)))
    if evidence_mode == 'caller' or discovered_url_count <= 0:
        return 1.0
    if evidence_mode == 'discovered' or caller_url_count <= 0:
        return round(factor, 3)
    total = caller_url_count + discovered_url_count
    blended = (caller_url_count * 1.0 + discovered_url_count * factor) / total
    return round(blended, 3)
