from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ReviewFlag = Literal["ready_for_review", "needs_human_review"]


@dataclass(frozen=True)
class ICPProfile:
    key: str
    name: str
    description: str
    target_segments: list[str]
    pain_points: list[str]
    buying_signals: list[str]
    disqualifiers: list[str]
    approved_outreach_angles: list[str]
    risk_notes: list[str]


@dataclass(frozen=True)
class SourceEvidence:
    claim: str
    source_url: str
    source_type: str
    retrieved_at: str
    grounding_passed: bool = False
    finding_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchFindings:
    company_name: str
    domain: str
    findings: list[SourceEvidence]
    grounding_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "domain": self.domain,
            "findings": [finding.to_dict() for finding in self.findings],
            "grounding_passed": self.grounding_passed,
        }


@dataclass(frozen=True)
class AnalystRationale:
    fit_score: int
    pain_point_match: str
    buying_trigger: str
    risk_flags: list[str]
    recommended_angle: str
    confidence: float
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutreachDraft:
    subject: str
    body: str
    confidence: float
    review_flag: ReviewFlag
    evidence_refs: list[str]
    validation_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CrewResult:
    research: ResearchFindings
    analysis: AnalystRationale
    draft: OutreachDraft
    status: str
    token_estimate: int
    latency_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "research": self.research.to_dict(),
            "analysis": self.analysis.to_dict(),
            "draft": self.draft.to_dict(),
            "status": self.status,
            "token_estimate": self.token_estimate,
            "latency_ms": self.latency_ms,
        }
