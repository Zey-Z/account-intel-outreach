from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse

from account_intel.models import ICPProfile, SourceEvidence


_FINDING_KEYWORDS = {
    "analytics",
    "benefits",
    "care",
    "claims",
    "clients",
    "customer",
    "efficiency",
    "engagement",
    "health",
    "healthcare",
    "insurance",
    "member",
    "members",
    "operations",
    "patients",
    "payer",
    "provider",
    "service",
    "support",
    "workflow",
}


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


class TavilyResearchClient:
    """Research client that reads public web pages through Tavily Search and Extract."""

    def __init__(self, api_key: str, sdk_client: Any | None = None, max_results: int = 5):
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required when RESEARCH_MODE=tavily.")
        self.max_results = max_results
        if sdk_client is not None:
            self.client = sdk_client
        else:
            try:
                from tavily import TavilyClient
            except ModuleNotFoundError as exc:
                raise RuntimeError("Install tavily-python to use RESEARCH_MODE=tavily.") from exc
            self.client = TavilyClient(api_key=api_key)

    def search_and_extract(
        self,
        company_name: str,
        domain: str | None,
        profile: ICPProfile,
    ) -> list[ResearchPage]:
        query = build_tavily_query(company_name, domain, profile)
        search_response = self.client.search(
            query=query,
            search_depth="basic",
            max_results=self.max_results,
            include_raw_content=False,
            include_domains=domain_variants(domain),
        )
        urls = _urls_from_search(search_response)[: self.max_results]
        if not urls:
            return []
        extract_response = self.client.extract(
            urls=urls,
            extract_depth="basic",
            format="text",
            query=query,
            chunks_per_source=3,
        )
        pages: list[ResearchPage] = []
        for result in extract_response.get("results", []):
            url = str(result.get("url", "")).strip()
            raw_content = str(result.get("raw_content", "")).strip()
            if not url or not raw_content:
                continue
            pages.append(
                ResearchPage(
                    url=url,
                    source_type=classify_source_type(url, domain),
                    text=raw_content,
                )
            )
        return pages


def build_research_client(mode: str | None = None, api_key: str | None = None) -> ResearchClient:
    selected_mode = (mode or os.getenv("RESEARCH_MODE", "offline")).strip().lower()
    if selected_mode in {"offline", "fixture", "mock"}:
        return OfflineResearchClient()
    if selected_mode == "tavily":
        selected_key = api_key if api_key is not None else os.getenv("TAVILY_API_KEY", "")
        return TavilyResearchClient(api_key=selected_key)
    raise ValueError(f"Unsupported research mode: {selected_mode}")


def build_tavily_query(company_name: str, domain: str | None, profile: ICPProfile) -> str:
    if "health" in profile.key or "health" in profile.name.lower():
        return f"{company_name} company healthcare operations member support"
    segment = profile.target_segments[0] if profile.target_segments else "operations"
    return f"{company_name} company {segment} operations support"


def domain_variants(domain: str | None) -> list[str]:
    if not domain:
        return []
    clean_domain = domain.lower().replace("https://", "").replace("http://", "").strip("/")
    bare_domain = clean_domain.removeprefix("www.")
    return [bare_domain, f"www.{bare_domain}"]


def classify_source_type(url: str, domain: str | None) -> str:
    parsed = urlparse(url.lower())
    path = parsed.path
    if any(marker in path for marker in ("career", "jobs", "job-openings")):
        return "job_post"
    if any(marker in path for marker in ("press", "press-release", "press-releases")):
        return "press_release"
    if any(marker in path for marker in ("news", "blog", "insight", "article")):
        return "news"
    if domain and domain.lower().replace("www.", "") in parsed.netloc.replace("www.", ""):
        return "company_website"
    return "news"


def _urls_from_search(search_response: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for result in search_response.get("results", []):
        url = str(result.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def pages_to_candidate_findings(company_name: str, pages: list[ResearchPage]) -> list[SourceEvidence]:
    findings: list[SourceEvidence] = []
    for index, page in enumerate(pages, start=1):
        claim = select_research_claim(company_name, page.text)
        findings.append(
            SourceEvidence(
                finding_id=f"finding_{index}",
                claim=claim,
                source_url=page.url,
                source_type=page.source_type,
                retrieved_at=_now(),
                grounding_passed=False,
            )
        )
    return findings


def select_research_claim(company_name: str, text: str) -> str:
    candidates = _candidate_text_units(text)
    if not candidates:
        return f"{company_name} has public company information available."
    return max(candidates, key=lambda candidate: _claim_score(company_name, candidate))


def _candidate_text_units(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned: list[str] = []
    for piece in pieces:
        normalized = " ".join(piece.split()).strip()
        if not _is_useful_claim_candidate(normalized):
            continue
        cleaned.append(normalized)
    return cleaned


def _is_useful_claim_candidate(text: str) -> bool:
    if len(text) < 45:
        return False
    if re.search(r"\d{1,3}-\d{3}-\d{4}", text):
        return False
    if len(text.split()) < 7:
        return False
    return True


def _claim_score(company_name: str, text: str) -> int:
    lower_text = text.lower()
    score = sum(2 for keyword in _FINDING_KEYWORDS if keyword in lower_text)
    if company_name.split()[0].lower() in lower_text:
        score += 2
    if text.endswith((".", "!", "?")):
        score += 1
    return score
