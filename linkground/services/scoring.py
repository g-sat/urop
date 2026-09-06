from __future__ import annotations
import re
DISCOURSE_PREFIXES = ('Notably, ', 'Crucially, ', 'As documented, ', 'Records show ', 'Analyses verify that ', 'Studies confirm ', 'Data implies ', 'Historians note ', 'Scholars agree ', 'Systems map that ')
PARTIAL_MARKERS = (', and it ', ', and they ', ', meaning ', ', which ', ', asserting ', ', intending ', ', explicitly stating ', ', proving ', ', claiming ')

def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

def strip_discourse_prefix(statement: str) -> str:
    text = statement.strip()
    for prefix in DISCOURSE_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text

def infer_claim_count(statement: str) -> int:
    lowered = f' {statement.lower()}'
    return 2 if any((marker in lowered for marker in PARTIAL_MARKERS)) else 1

def has_parseable_score(text: str) -> bool:
    if re.search('groundedness\\s*[:=]\\s*[01](?:\\.\\d+)?', text or '', flags=re.IGNORECASE):
        return True
    if re.search('SUPPORT\\s*[:=]\\s*[01](?:\\.\\d+)?', text or '', flags=re.IGNORECASE):
        return True
    if re.search('->\\s*\\[?\\s*(TRUE|FALSE)\\s*]?', text or '', flags=re.IGNORECASE):
        return True
    return False

def parse_groundedness(model_output: str, expected_claims: int=1) -> float:
    text = model_output or ''
    overall = re.search('(?:overall[_ ]?)?groundedness\\s*[:=]\\s*([01](?:\\.\\d+)?)', text, flags=re.IGNORECASE)
    if overall:
        return round(clamp01(float(overall.group(1))), 2)
    support_scores: list[float] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        support_match = re.search('SUPPORT\\s*[:=]\\s*([01](?:\\.\\d+)?)', line, flags=re.IGNORECASE)
        if support_match:
            support_scores.append(clamp01(float(support_match.group(1))))
            continue
        arrow_score = re.search('->\\s*([01](?:\\.\\d+)?)\\b', line)
        if arrow_score and 'claim' in line.lower():
            support_scores.append(clamp01(float(arrow_score.group(1))))
            continue
        if re.search('->\\s*\\[?\\s*TRUE\\s*]?', line, flags=re.IGNORECASE) and (not re.search('->\\s*\\[?\\s*FALSE\\s*]?', line, flags=re.IGNORECASE)):
            support_scores.append(1.0)
        elif re.search('->\\s*\\[?\\s*FALSE\\s*]?', line, flags=re.IGNORECASE):
            support_scores.append(0.0)
    if support_scores:
        trimmed = support_scores[:max(1, expected_claims)]
        return round(sum(trimmed) / len(trimmed), 2)
    return 0.5
