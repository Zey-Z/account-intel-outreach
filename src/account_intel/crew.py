from __future__ import annotations

import os
import time

from account_intel.crewai_runtime import CrewAIAccountRuntime
from account_intel.grounding import ground_findings
from account_intel.models import (
    AnalystRationale,
    CrewResult,
    ICPProfile,
    OutreachDraft,
    ResearchFindings,
)
from account_intel.research_tools import (
    OfflineResearchClient,
    ResearchClient,
    pages_to_candidate_findings,
)
from account_intel.validation import review_flag_for, validate_writer_evidence


def _has_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _has_phi_or_clinical_risk(text: str) -> bool:
    risk_phrases = {
        "clinical diagnosis",
        "diagnosis",
        "medical record",
        "patient data",
        "patient records",
        "phi",
        "protected health information",
        "treatment plan",
    }
    return any(phrase in text for phrase in risk_phrases)


class AccountIntelligenceCrew:
    """Small orchestration boundary for the Researcher -> Analyst -> Writer flow."""

    def __init__(
        self,
        research_client: ResearchClient | None = None,
        runtime_mode: str | None = None,
        crewai_module: object | None = None,
        llm: object | None = None,
    ):
        self.research_client = research_client or OfflineResearchClient()
        self.runtime_mode = (runtime_mode or os.getenv("AGENT_RUNTIME", "deterministic")).strip().lower()
        self.crewai_module = crewai_module
        self.llm = llm or os.getenv("CREWAI_LLM") or None

    def run_company(
        self,
        company_name: str,
        domain: str | None,
        profile: ICPProfile,
    ) -> CrewResult:
        if self.runtime_mode in {"crewai", "crew_ai", "agent"}:
            return CrewAIAccountRuntime(
                research_client=self.research_client,
                crewai_module=self.crewai_module,
                llm=self.llm,
            ).run_company(company_name, domain, profile)
        started = time.perf_counter()
        pages = self.research_client.search_and_extract(company_name, domain, profile)
        extracted_text = {page.url: page.text for page in pages}
        candidate_findings = pages_to_candidate_findings(company_name, pages)
        grounded_findings = ground_findings(candidate_findings, extracted_text)
        research = ResearchFindings(
            company_name=company_name,
            domain=domain or "",
            findings=grounded_findings,
            grounding_passed=len(grounded_findings) >= 3,
        )
        analysis = self._analyze(profile, research)
        draft = self._write_draft(company_name, profile, analysis, research)
        draft = validate_writer_evidence(draft, grounded_findings)
        status = self._status_for(research, analysis, draft)
        latency_ms = int((time.perf_counter() - started) * 1000)
        token_estimate = self._estimate_tokens(research, analysis, draft)
        return CrewResult(research, analysis, draft, status, token_estimate, latency_ms)

    @staticmethod
    def _analyze(profile: ICPProfile, research: ResearchFindings) -> AnalystRationale:
        joined_claims = " ".join(finding.claim.lower() for finding in research.findings)
        source_types = {finding.source_type for finding in research.findings}
        score = 40
        matched_points: list[str] = []
        for point in profile.pain_points:
            point_words = {word for word in point.lower().split() if len(word) > 4}
            if point_words and any(word in joined_claims for word in point_words):
                score += 6
                matched_points.append(point)
        if _has_any(joined_claims, {"member", "members"}) and _has_any(
            joined_claims, {"support", "care", "engagement", "education"}
        ):
            score += 18
            _append_unique(matched_points, "member support triage")
        if _has_any(joined_claims, {"healthcare", "health"}) and _has_any(
            joined_claims, {"operations", "efficiency", "clients", "technology", "platform"}
        ):
            score += 14
            _append_unique(matched_points, "healthcare operations workflow support")
        if _has_any(joined_claims, {"claims", "payer", "provider", "benefits"}):
            score += 10
        if _has_any(joined_claims, {"automation", "ai", "tools", "technology", "platform"}):
            score += 8
        for signal in profile.buying_signals:
            signal_words = {word for word in signal.lower().split() if len(word) > 4}
            if signal_words and any(word in joined_claims for word in signal_words):
                score += 6
        if "job_post" in source_types:
            score += 6
        if "press_release" in source_types:
            score += 6
        risk_flags = []
        if _has_phi_or_clinical_risk(joined_claims):
            risk_flags.append("Potential clinical/PHI-adjacent language; keep demo public-data-only.")
            score = min(score, 68)
        fit_score = max(0, min(88, score))
        confidence = 0.82 if research.grounding_passed and fit_score >= 60 else 0.55
        evidence_refs = [finding.finding_id or finding.source_url for finding in research.findings]
        buying_trigger = "Public signals suggest healthcare operations workflow activity."
        if "job_post" in source_types:
            buying_trigger = "Public hiring and healthcare operations signals suggest workflow support needs."
        elif "press_release" in source_types:
            buying_trigger = "Public company updates suggest healthcare operations workflow activity."
        return AnalystRationale(
            fit_score=fit_score,
            pain_point_match=", ".join(matched_points[:3]) or "No strong pain point match found.",
            buying_trigger=buying_trigger,
            risk_flags=risk_flags,
            recommended_angle=profile.approved_outreach_angles[0],
            confidence=confidence,
            evidence_refs=evidence_refs,
        )

    @staticmethod
    def _write_draft(
        company_name: str,
        profile: ICPProfile,
        analysis: AnalystRationale,
        research: ResearchFindings,
    ) -> OutreachDraft:
        first_claim = research.findings[0].claim if research.findings else f"{company_name} has public operations signals."
        second_claim = research.findings[1].claim if len(research.findings) > 1 else first_claim
        review_flag = review_flag_for(analysis.confidence, research.grounding_passed, analysis.fit_score)
        body = (
            "Hi {first_name},\n\n"
            f"I noticed {first_claim} {second_claim} "
            f"That suggests a fit for {analysis.recommended_angle}. "
            "Worth comparing notes on reducing manual review while keeping human approval in the loop?\n\n"
            "Best,\nZeyu"
        )
        return OutreachDraft(
            subject=f"Idea for {company_name} operations workflows",
            body=body,
            confidence=analysis.confidence,
            review_flag=review_flag,  # type: ignore[arg-type]
            evidence_refs=analysis.evidence_refs,
        )

    @staticmethod
    def _status_for(research: ResearchFindings, analysis: AnalystRationale, draft: OutreachDraft) -> str:
        if not research.grounding_passed:
            return "needs_human_research"
        if analysis.fit_score < 45:
            return "archived"
        if draft.review_flag == "ready_for_review":
            return "sent_to_review"
        return "needs_human_research"

    @staticmethod
    def _estimate_tokens(research: ResearchFindings, analysis: AnalystRationale, draft: OutreachDraft) -> int:
        text = str(research.to_dict()) + str(analysis.to_dict()) + str(draft.to_dict())
        return max(1, len(text) // 4)
