import unittest
from pathlib import Path


class AnalysisQualityTests(unittest.TestCase):
    def _profile(self):
        from account_intel.config import load_icp_profiles

        return load_icp_profiles(Path("icp_profiles.yaml"))["healthcare_insurance_ops"]

    def test_strong_healthcare_operations_evidence_scores_as_good_fit(self):
        from account_intel.crew import AccountIntelligenceCrew
        from account_intel.models import ResearchFindings, SourceEvidence

        research = ResearchFindings(
            company_name="Oscar Health",
            domain="hioscar.com",
            grounding_passed=True,
            findings=[
                SourceEvidence(
                    finding_id="finding_1",
                    claim=(
                        "Helping healthcare clients drive improved efficiency, growth and "
                        "superior engagement with their members and patients."
                    ),
                    source_url="https://www.hioscar.com/plus-oscar",
                    source_type="company_website",
                    retrieved_at="2026-05-25T00:00:00Z",
                    grounding_passed=True,
                ),
                SourceEvidence(
                    finding_id="finding_2",
                    claim=(
                        "As a personal health guide, you make lives better by providing "
                        "exceptional support and education to our members."
                    ),
                    source_url="https://www.hioscar.com/careers/member-care",
                    source_type="job_post",
                    retrieved_at="2026-05-25T00:00:00Z",
                    grounding_passed=True,
                ),
                SourceEvidence(
                    finding_id="finding_3",
                    claim=(
                        "Oscar is a leading healthcare technology company built around "
                        "a full stack technology platform and serving members."
                    ),
                    source_url="https://ir.hioscar.com/news",
                    source_type="press_release",
                    retrieved_at="2026-05-25T00:00:00Z",
                    grounding_passed=True,
                ),
            ],
        )

        analysis = AccountIntelligenceCrew._analyze(self._profile(), research)

        self.assertGreaterEqual(analysis.fit_score, 70)
        self.assertLessEqual(analysis.fit_score, 88)
        self.assertGreaterEqual(analysis.confidence, 0.75)
        self.assertIn("member support triage", analysis.pain_point_match)
        self.assertIn("healthcare operations", analysis.buying_trigger.lower())
        self.assertEqual(analysis.evidence_refs, ["finding_1", "finding_2", "finding_3"])

    def test_public_patient_language_alone_is_not_phi_risk(self):
        from account_intel.crew import AccountIntelligenceCrew
        from account_intel.models import ResearchFindings, SourceEvidence

        research = ResearchFindings(
            company_name="Oscar Health",
            domain="hioscar.com",
            grounding_passed=True,
            findings=[
                SourceEvidence(
                    finding_id="finding_1",
                    claim="Oscar helps members and patients find quality care they can afford.",
                    source_url="https://www.hioscar.com/about",
                    source_type="company_website",
                    retrieved_at="2026-05-25T00:00:00Z",
                    grounding_passed=True,
                )
            ],
        )

        analysis = AccountIntelligenceCrew._analyze(self._profile(), research)

        self.assertEqual(analysis.risk_flags, [])


if __name__ == "__main__":
    unittest.main()
