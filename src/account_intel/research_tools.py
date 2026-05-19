from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from account_intel.models import ICPProfile, SourceEvidence


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ResearchPage:
    url: str
    source_type: str
    text: str


class ResearchClient(Protocol):
    def search_and_extract(self, company_name: str, domain: str | None, profile: ICPProfile) -> list[ResearchPage]:
        ...


class OfflineResearchClient:
    """Deterministic research fixture for local learning and tests."""

    def search_and_extract(
        self,
        company_name: str,
        domain: str | None,
        profile: ICPProfile,
    ) -> list[ResearchPage]:
        safe_domain = domain or f"{company_name.lower().replace(' ', '')}.example"
        base_url = f"https://{safe_domain}"
        return [
            ResearchPage(
                url=base_url,
                source_type="company_website",
                text=(
                    f"{company_name} provides claims analytics for payer operations teams. "
                    f"{company_name} supports member support triage and document intake workflows."
                ),
            ),
            ResearchPage(
                url=f"{base_url}/careers",
                source_type="job_post",
                text=(
                    f"{company_name} is hiring operations and customer support roles for "
                    "healthcare workflow teams."
                ),
            ),
            ResearchPage(
                url=f"{base_url}/news",
                source_type="news",
                text=(
                    f"{company_name} publishes updates about automation, claims review, "
                    "and payer operations support."
                ),
            ),
        ]


def pages_to_candidate_findings(company_name: str, pages: list[ResearchPage]) -> list[SourceEvidence]:
    findings: list[SourceEvidence] = []
    for index, page in enumerate(pages, start=1):
        first_sentence = page.text.split(".")[0].strip() + "."
        findings.append(
            SourceEvidence(
                finding_id=f"finding_{index}",
                claim=first_sentence,
                source_url=page.url,
                source_type=page.source_type,
                retrieved_at=_now(),
                grounding_passed=False,
            )
        )
    return findings
