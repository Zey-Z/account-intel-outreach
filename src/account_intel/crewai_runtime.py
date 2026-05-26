from __future__ import annotations

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from account_intel.grounding import ground_findings
from account_intel.models import (
    AnalystRationale,
    CrewResult,
    ICPProfile,
    OutreachDraft,
    ResearchFindings,
    SourceEvidence,
)
from account_intel.research_tools import (
    OfflineResearchClient,
    ResearchClient,
    pages_to_candidate_findings,
)
from account_intel.validation import review_flag_for, validate_writer_evidence


class CrewAISourceEvidence(BaseModel):
    claim: str = Field(description="A factual company claim copied from the provided evidence.")
    source_url: str = Field(description="The exact URL that supports the claim.")
    source_type: str = Field(description="company_website, news, job_post, or press_release.")
    retrieved_at: str
    grounding_passed: bool = True


class CrewAIResearchOutput(BaseModel):
    company_name: str
    domain: str
    findings: list[CrewAISourceEvidence] = Field(min_length=1)
    grounding_passed: bool


class CrewAIAnalysisOutput(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    pain_point_match: str
    buying_trigger: str
    risk_flags: list[str] = Field(default_factory=list)
    recommended_angle: str
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)


class CrewAIOutreachOutput(BaseModel):
    subject: str
    body: str
    confidence: float = Field(ge=0, le=1)
    review_flag: Literal["ready_for_review", "needs_human_review"]
    evidence_refs: list[str] = Field(default_factory=list)


class CrewAIUnavailableError(RuntimeError):
    pass


def build_crewai_prompt_context(company_name: str, domain: str | None, profile: ICPProfile) -> str:
    """Prepare shared task context for the CrewAI runtime."""

    return (
        f"Company: {company_name}\n"
        f"Domain: {domain or 'unknown'}\n"
        f"ICP profile: {profile.name}\n"
        f"Target segments: {', '.join(profile.target_segments)}\n"
        f"Pain points: {', '.join(profile.pain_points)}\n"
        f"Buying signals: {', '.join(profile.buying_signals)}\n"
        f"Disqualifiers: {', '.join(profile.disqualifiers)}\n"
        "Scope: public company information only; no PHI; no patient data; no automated email sending."
    )


def crewai_dependency_available() -> bool:
    try:
        import crewai  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


class CrewAIAccountRuntime:
    """Real CrewAI Agent/Task/Crew runtime behind the existing workflow contract."""

    def __init__(
        self,
        research_client: ResearchClient | None = None,
        crewai_module: Any | None = None,
        llm: Any | None = None,
        verbose: bool = False,
    ):
        self.research_client = research_client or OfflineResearchClient()
        self.crewai = crewai_module or self._load_crewai_module()
        self.llm = llm
        self.verbose = verbose

    def run_company(self, company_name: str, domain: str | None, profile: ICPProfile) -> CrewResult:
        started = time.perf_counter()
        pages = self.research_client.search_and_extract(company_name, domain, profile)
        extracted_text = {page.url: page.text for page in pages}
        pre_grounded_findings = ground_findings(
            pages_to_candidate_findings(company_name, pages),
            extracted_text,
        )
        researcher, analyst, writer = self._build_agents()
        research_task, analysis_task, writer_task = self._build_tasks(
            company_name=company_name,
            domain=domain,
            profile=profile,
            evidence_json=json.dumps(
                [finding.to_dict() for finding in pre_grounded_findings],
                indent=2,
                ensure_ascii=True,
            ),
            researcher=researcher,
            analyst=analyst,
            writer=writer,
        )
        crew = self.crewai.Crew(
            agents=[researcher, analyst, writer],
            tasks=[research_task, analysis_task, writer_task],
            process=self.crewai.Process.sequential,
            verbose=self.verbose,
        )
        crew_output = crew.kickoff(
            inputs={
                "company_name": company_name,
                "domain": domain or "",
                "icp_profile": profile.key,
            }
        )
        research = self._research_from_task(
            research_task,
            company_name=company_name,
            domain=domain,
            extracted_text=extracted_text,
            pre_grounded_findings=pre_grounded_findings,
        )
        analysis = self._analysis_from_task(analysis_task, profile, research)
        draft = self._draft_from_task(writer_task, analysis, research)
        status = self._status_for(research, analysis, draft)
        latency_ms = int((time.perf_counter() - started) * 1000)
        token_estimate = _extract_token_estimate(crew_output) or self._estimate_tokens(research, analysis, draft)
        return CrewResult(research, analysis, draft, status, token_estimate, latency_ms)

    @staticmethod
    def _load_crewai_module() -> Any:
        try:
            from crewai import Agent, Crew, Process, Task
        except ModuleNotFoundError as exc:
            raise CrewAIUnavailableError("Install crewai or use AGENT_RUNTIME=deterministic.") from exc
        return type("CrewAIModule", (), {"Agent": Agent, "Task": Task, "Crew": Crew, "Process": Process})

    def _build_agents(self) -> tuple[Any, Any, Any]:
        return (
            self._agent(
                role="Senior Account Researcher",
                goal="Turn provided public web evidence into source-grounded account findings.",
                backstory=(
                    "You are a careful account researcher. You never invent URLs, numbers, customers, "
                    "or product claims. You only use the evidence provided by the harness."
                ),
            ),
            self._agent(
                role="GTM Fit Strategist",
                goal="Evaluate ICP fit using only the Researcher findings and the selected ICP profile.",
                backstory=(
                    "You understand healthcare operations, insurance workflows, and human-approved "
                    "AI automation. You score conservatively and explain the decision."
                ),
            ),
            self._agent(
                role="Personalized Outreach Copywriter",
                goal="Draft a concise outreach email using only cited research findings.",
                backstory=(
                    "You write practical B2B outreach drafts. You do not send emails, and you do not add "
                    "facts that were not present in the Researcher output."
                ),
            ),
        )

    def _agent(self, **kwargs: Any) -> Any:
        kwargs.update({"allow_delegation": False, "verbose": self.verbose})
        if self.llm is not None:
            kwargs["llm"] = self.llm
        return self.crewai.Agent(**kwargs)

    def _build_tasks(
        self,
        company_name: str,
        domain: str | None,
        profile: ICPProfile,
        evidence_json: str,
        researcher: Any,
        analyst: Any,
        writer: Any,
    ) -> tuple[Any, Any, Any]:
        context = build_crewai_prompt_context(company_name, domain, profile)
        research_task = self.crewai.Task(
            description=(
                f"{context}\n\n"
                "Use the provided grounded evidence only. Return 3 to 5 findings when available. "
                "Do not create new source URLs.\n\n"
                f"Grounded evidence JSON:\n{evidence_json}"
            ),
            expected_output="Structured account research with source-backed findings.",
            agent=researcher,
            output_pydantic=CrewAIResearchOutput,
        )
        analysis_task = self.crewai.Task(
            description=(
                f"{context}\n\n"
                "Using the Researcher output and ICP profile, score the company from 0 to 100. "
                "Mention pain-point fit, buying trigger, risk flags, recommended angle, confidence, "
                "and evidence_refs."
            ),
            expected_output="Structured ICP fit score and rationale.",
            agent=analyst,
            context=[research_task],
            output_pydantic=CrewAIAnalysisOutput,
        )
        writer_task = self.crewai.Task(
            description=(
                f"{context}\n\n"
                "Draft a short outreach email. Do not send it. Use only facts from Researcher findings. "
                "Set review_flag to needs_human_review when confidence is low or evidence is thin."
            ),
            expected_output="Structured outreach draft with subject, body, confidence, review_flag, and evidence_refs.",
            agent=writer,
            context=[research_task, analysis_task],
            output_pydantic=CrewAIOutreachOutput,
        )
        return research_task, analysis_task, writer_task

    @staticmethod
    def _research_from_task(
        task: Any,
        company_name: str,
        domain: str | None,
        extracted_text: dict[str, str],
        pre_grounded_findings: list[SourceEvidence],
    ) -> ResearchFindings:
        output = _task_pydantic(task)
        if output is None:
            findings = pre_grounded_findings
        else:
            candidate_findings = [
                SourceEvidence(
                    claim=finding.claim,
                    source_url=finding.source_url,
                    source_type=finding.source_type,
                    retrieved_at=finding.retrieved_at,
                    grounding_passed=False,
                )
                for finding in output.findings
                if finding.source_url in extracted_text
            ]
            findings = ground_findings(candidate_findings, extracted_text)
            if not findings:
                findings = pre_grounded_findings
        return ResearchFindings(
            company_name=company_name,
            domain=domain or "",
            findings=findings,
            grounding_passed=len(findings) >= 3,
        )

    @staticmethod
    def _analysis_from_task(task: Any, profile: ICPProfile, research: ResearchFindings) -> AnalystRationale:
        output = _task_pydantic(task)
        evidence_refs = [finding.finding_id or finding.source_url for finding in research.findings]
        if output is None:
            return AnalystRationale(
                fit_score=0,
                pain_point_match="CrewAI analysis output was missing.",
                buying_trigger="No reliable buying trigger.",
                risk_flags=["CrewAI analysis output missing."],
                recommended_angle=profile.approved_outreach_angles[0],
                confidence=0.0,
                evidence_refs=evidence_refs,
            )
        return AnalystRationale(
            fit_score=max(0, min(100, int(output.fit_score))),
            pain_point_match=output.pain_point_match,
            buying_trigger=output.buying_trigger,
            risk_flags=output.risk_flags,
            recommended_angle=output.recommended_angle or profile.approved_outreach_angles[0],
            confidence=max(0.0, min(1.0, float(output.confidence))),
            evidence_refs=output.evidence_refs or evidence_refs,
        )

    @staticmethod
    def _draft_from_task(task: Any, analysis: AnalystRationale, research: ResearchFindings) -> OutreachDraft:
        output = _task_pydantic(task)
        if output is None:
            draft = OutreachDraft(
                subject="Human review needed for outreach draft",
                body="Draft generation did not return a structured output.",
                confidence=0.0,
                review_flag="needs_human_review",
                evidence_refs=analysis.evidence_refs,
                validation_notes="CrewAI writer output missing.",
            )
        else:
            review_flag = review_flag_for(output.confidence, research.grounding_passed, analysis.fit_score)
            if output.review_flag == "needs_human_review":
                review_flag = "needs_human_review"
            draft = OutreachDraft(
                subject=output.subject,
                body=output.body,
                confidence=max(0.0, min(1.0, float(output.confidence))),
                review_flag=review_flag,  # type: ignore[arg-type]
                evidence_refs=output.evidence_refs or analysis.evidence_refs,
            )
        return validate_writer_evidence(draft, research.findings)

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


def _task_pydantic(task: Any) -> Any | None:
    output = getattr(task, "output", None)
    return getattr(output, "pydantic", None)


def _extract_token_estimate(crew_output: Any) -> int | None:
    for attr in ("usage_metrics", "token_usage", "metrics"):
        metrics = getattr(crew_output, attr, None)
        if metrics is None:
            continue
        if isinstance(metrics, dict):
            for key in ("total_tokens", "total_token_usage", "tokens"):
                value = metrics.get(key)
                if isinstance(value, int):
                    return value
        value = getattr(metrics, "total_tokens", None)
        if isinstance(value, int):
            return value
    return None
