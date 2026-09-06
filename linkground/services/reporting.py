from __future__ import annotations
from typing import Any

def build_research_block(*, evidence_mode: str, discovery_weight: float, groundedness_score: float, authority_multiplier: float, trust_index: float, caller_url_count: int, discovered_url_count: int) -> dict[str, Any]:
    prestige_inflation = round(max(0.0, trust_index - groundedness_score), 3)
    ethics_flags: list[str] = ['primary_metric_is_authority_agnostic_support', 'prestige_is_not_correctness']
    if evidence_mode in {'discovered', 'mixed'}:
        ethics_flags.append('trusted_seed_discovery_active')
        ethics_flags.append('english_reference_source_prior_possible')
    if discovery_weight < 1.0:
        ethics_flags.append(f'discovery_discount_applied:{discovery_weight}')
    if authority_multiplier >= 1.1 and groundedness_score <= 0.4:
        ethics_flags.append('high_prestige_low_support_risk')
    if caller_url_count == 0:
        ethics_flags.append('no_caller_citations')
    if caller_url_count > 0 and discovered_url_count == 0:
        citation_path = 'caller_attributed'
    elif caller_url_count == 0 and discovered_url_count > 0:
        citation_path = 'discovery_only'
    elif caller_url_count > 0 and discovered_url_count > 0:
        citation_path = 'mixed_attribution'
    else:
        citation_path = 'no_evidence'
    return {'framework': 'LCSE', 'version': '3.0.0', 'spines': ['A_prestige_support_confound', 'B_citation_attribution', 'C_authority_ethics'], 'support': groundedness_score, 'prestige': authority_multiplier, 'prestige_inflation': prestige_inflation, 'citation_path': citation_path, 'ethics_flags': ethics_flags, 'reporting_rule': 'Lead with support (groundedness_score). Report prestige separately. Do not treat trust_index as accuracy.'}
