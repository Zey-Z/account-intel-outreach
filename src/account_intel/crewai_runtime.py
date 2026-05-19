from __future__ import annotations

from account_intel.models import ICPProfile


def build_crewai_prompt_context(company_name: str, domain: str | None, profile: ICPProfile) -> str:
    """Prepare the context that a real CrewAI Task should receive.

    The local MVP uses deterministic Python classes so it can be tested without
    LLM keys. This function documents the exact payload that the CrewAI runtime
    should preserve when we switch the agent brain to real CrewAI Agent/Task
    objects.
    """

    return (
        f"Company: {company_name}\n"
        f"Domain: {domain or 'unknown'}\n"
        f"ICP profile: {profile.name}\n"
        f"Target segments: {', '.join(profile.target_segments)}\n"
        f"Pain points: {', '.join(profile.pain_points)}\n"
        f"Buying signals: {', '.join(profile.buying_signals)}\n"
        f"Disqualifiers: {', '.join(profile.disqualifiers)}\n"
        "Scope: public company information only; no PHI; no automated email sending."
    )


def crewai_dependency_available() -> bool:
    try:
        import crewai  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True
