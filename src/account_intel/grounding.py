from __future__ import annotations

import re

from account_intel.models import SourceEvidence


_STOPWORDS = {
    "about",
    "across",
    "also",
    "and",
    "into",
    "that",
    "their",
    "this",
    "with",
    "work",
    "works",
    "uses",
    "recently",
}


def significant_tokens(text: str) -> set[str]:
    tokens = {token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text)}
    return {token for token in tokens if token not in _STOPWORDS}


def claim_is_grounded(claim: str, source_text: str, min_overlap: float = 0.45) -> bool:
    claim_tokens = significant_tokens(claim)
    source_tokens = significant_tokens(source_text)
    if not claim_tokens or not source_tokens:
        return False
    overlap = claim_tokens & source_tokens
    return len(overlap) / len(claim_tokens) >= min_overlap


def ground_findings(
    findings: list[SourceEvidence],
    extracted_text_by_url: dict[str, str],
) -> list[SourceEvidence]:
    grounded: list[SourceEvidence] = []
    for finding in findings:
        source_text = extracted_text_by_url.get(finding.source_url, "")
        if claim_is_grounded(finding.claim, source_text):
            grounded.append(
                SourceEvidence(
                    claim=finding.claim,
                    source_url=finding.source_url,
                    source_type=finding.source_type,
                    retrieved_at=finding.retrieved_at,
                    grounding_passed=True,
                    finding_id=finding.finding_id,
                )
            )
    return grounded
