from __future__ import annotations

from dataclasses import replace

from account_intel.grounding import significant_tokens
from account_intel.models import OutreachDraft, SourceEvidence


_GENERIC_OUTREACH_WORDS = {
    "able",
    "account",
    "across",
    "ai-assisted",
    "angle",
    "around",
    "assisted",
    "best",
    "brief",
    "comparing",
    "compare",
    "could",
    "exception",
    "first",
    "follow",
    "help",
    "human",
    "approval",
    "keeping",
    "loop",
    "manual",
    "might",
    "name",
    "notes",
    "noticed",
    "operations",
    "process",
    "reduce",
    "reducing",
    "review",
    "suggests",
    "team",
    "teams",
    "triage",
    "workflow",
    "workflows",
    "would",
    "worth",
    "while",
    "zeyu",
}


def validate_writer_evidence(
    draft: OutreachDraft,
    findings: list[SourceEvidence],
    max_unsupported_terms: int = 3,
) -> OutreachDraft:
    evidence_text = " ".join(finding.claim for finding in findings)
    evidence_tokens = significant_tokens(evidence_text)
    draft_tokens = significant_tokens(draft.body)
    unsupported = sorted(
        token
        for token in draft_tokens - evidence_tokens
        if token not in _GENERIC_OUTREACH_WORDS
    )
    if len(unsupported) >= max_unsupported_terms:
        return replace(
            draft,
            review_flag="needs_human_review",
            validation_notes=(
                "Unsupported draft facts detected: " + ", ".join(unsupported[:8])
            ),
        )
    return draft


def review_flag_for(confidence: float, grounding_passed: bool, fit_score: int) -> str:
    if confidence >= 0.75 and grounding_passed and fit_score >= 60:
        return "ready_for_review"
    return "needs_human_review"
