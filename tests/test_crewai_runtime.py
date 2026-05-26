import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class FakeCrewAIModule:
    class Process:
        sequential = "sequential"

    created_agents = []
    created_tasks = []
    created_crews = []

    class Agent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            FakeCrewAIModule.created_agents.append(self)

    class Task:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.output = None
            FakeCrewAIModule.created_tasks.append(self)

    class Crew:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.tasks = kwargs["tasks"]
            FakeCrewAIModule.created_crews.append(self)

        def kickoff(self, inputs=None):
            research_model = self.tasks[0].kwargs["output_pydantic"]
            analysis_model = self.tasks[1].kwargs["output_pydantic"]
            draft_model = self.tasks[2].kwargs["output_pydantic"]
            finding_model = research_model.model_fields["findings"].annotation.__args__[0]
            self.tasks[0].output = types.SimpleNamespace(
                pydantic=research_model(
                    company_name="Northstar Health",
                    domain="northstar.example",
                    findings=[
                        finding_model(
                            claim="Northstar Health supports member support triage and document intake workflows.",
                            source_url="https://northstar.example",
                            source_type="company_website",
                            retrieved_at="2026-05-26T00:00:00Z",
                            grounding_passed=True,
                        ),
                        finding_model(
                            claim="Northstar Health is hiring operations and customer support roles for healthcare workflow teams.",
                            source_url="https://northstar.example/careers",
                            source_type="job_post",
                            retrieved_at="2026-05-26T00:00:00Z",
                            grounding_passed=True,
                        ),
                        finding_model(
                            claim="Northstar Health publishes updates about automation and payer operations support.",
                            source_url="https://northstar.example/news",
                            source_type="news",
                            retrieved_at="2026-05-26T00:00:00Z",
                            grounding_passed=True,
                        ),
                    ],
                    grounding_passed=True,
                )
            )
            self.tasks[1].output = types.SimpleNamespace(
                pydantic=analysis_model(
                    fit_score=84,
                    pain_point_match="member support triage",
                    buying_trigger="Hiring and public operations signals suggest workflow support needs.",
                    risk_flags=[],
                    recommended_angle="AI-assisted exception triage with human approval",
                    confidence=0.81,
                    evidence_refs=[
                        "https://northstar.example",
                        "https://northstar.example/careers",
                    ],
                )
            )
            self.tasks[2].output = types.SimpleNamespace(
                pydantic=draft_model(
                    subject="CrewAI generated subject",
                    body=(
                        "Hi {first_name},\n\n"
                        "I noticed Northstar Health supports member support triage and document intake workflows. "
                        "Worth comparing notes on AI-assisted exception triage with human approval?\n\n"
                        "Best,\nZeyu"
                    ),
                    confidence=0.81,
                    review_flag="ready_for_review",
                    evidence_refs=[
                        "https://northstar.example",
                        "https://northstar.example/careers",
                    ],
                )
            )
            return types.SimpleNamespace(usage_metrics={"total_tokens": 321})


class CrewAIRuntimeTests(unittest.TestCase):
    def setUp(self):
        FakeCrewAIModule.created_agents = []
        FakeCrewAIModule.created_tasks = []
        FakeCrewAIModule.created_crews = []

    def test_crewai_runtime_builds_three_agent_sequential_crew(self):
        from account_intel.config import load_icp_profiles
        from account_intel.crewai_runtime import CrewAIAccountRuntime
        from account_intel.research_tools import OfflineResearchClient

        profile = load_icp_profiles(Path("icp_profiles.yaml"))["healthcare_insurance_ops"]
        runtime = CrewAIAccountRuntime(
            research_client=OfflineResearchClient(),
            crewai_module=FakeCrewAIModule,
            llm="test-llm",
            verbose=False,
        )

        result = runtime.run_company("Northstar Health", "northstar.example", profile)

        self.assertEqual([agent.kwargs["role"] for agent in FakeCrewAIModule.created_agents], [
            "Senior Account Researcher",
            "GTM Fit Strategist",
            "Personalized Outreach Copywriter",
        ])
        self.assertEqual(len(FakeCrewAIModule.created_tasks), 3)
        self.assertIs(FakeCrewAIModule.created_tasks[1].kwargs["context"][0], FakeCrewAIModule.created_tasks[0])
        self.assertEqual(FakeCrewAIModule.created_crews[0].kwargs["process"], FakeCrewAIModule.Process.sequential)
        self.assertEqual(result.draft.subject, "CrewAI generated subject")
        self.assertEqual(result.status, "sent_to_review")
        self.assertEqual(result.token_estimate, 321)

    def test_account_intelligence_crew_routes_to_crewai_runtime_when_selected(self):
        from account_intel.config import load_icp_profiles
        from account_intel.crew import AccountIntelligenceCrew
        from account_intel.research_tools import OfflineResearchClient

        profile = load_icp_profiles(Path("icp_profiles.yaml"))["healthcare_insurance_ops"]
        crew = AccountIntelligenceCrew(
            research_client=OfflineResearchClient(),
            runtime_mode="crewai",
            crewai_module=FakeCrewAIModule,
            llm="test-llm",
        )

        result = crew.run_company("Northstar Health", "northstar.example", profile)

        self.assertEqual(len(FakeCrewAIModule.created_crews), 1)
        self.assertEqual(result.draft.subject, "CrewAI generated subject")


if __name__ == "__main__":
    unittest.main()
