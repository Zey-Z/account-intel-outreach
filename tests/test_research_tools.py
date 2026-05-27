import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class FakeTavilySdk:
    def __init__(self):
        self.search_calls = []
        self.extract_calls = []

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return {
            "results": [
                {"url": "https://www.centene.com/"},
                {"url": "https://www.centene.com/news/press-releases.html"},
                {"url": "https://www.centene.com/careers.html"},
            ]
        }

    def extract(self, **kwargs):
        self.extract_calls.append(kwargs)
        return {
            "results": [
                {
                    "url": "https://www.centene.com/",
                    "raw_content": "Centene provides healthcare programs and services for government-sponsored care.",
                },
                {
                    "url": "https://www.centene.com/news/press-releases.html",
                    "raw_content": "Centene announced updates about health plan operations and member support.",
                },
                {
                    "url": "https://www.centene.com/careers.html",
                    "raw_content": "Centene is hiring operations roles for healthcare service teams.",
                },
            ],
            "failed_results": [],
        }


class ResearchToolsTests(unittest.TestCase):
    def _profile(self):
        from account_intel.config import load_icp_profiles

        return load_icp_profiles(Path("icp_profiles.yaml"))["healthcare_insurance_ops"]

    def test_tavily_client_searches_then_extracts_pages(self):
        from account_intel.research_tools import TavilyResearchClient

        fake_sdk = FakeTavilySdk()
        client = TavilyResearchClient(api_key="test-key", sdk_client=fake_sdk, max_results=3)

        pages = client.search_and_extract("Centene", "centene.com", self._profile())

        self.assertEqual(len(pages), 3)
        self.assertEqual(pages[0].url, "https://www.centene.com/")
        self.assertEqual(pages[0].source_type, "company_website")
        self.assertEqual(pages[1].source_type, "press_release")
        self.assertEqual(pages[2].source_type, "job_post")
        self.assertIn("Centene", fake_sdk.search_calls[0]["query"])
        self.assertNotIn("site:", fake_sdk.search_calls[0]["query"])
        self.assertEqual(fake_sdk.search_calls[0]["include_domains"], ["centene.com", "www.centene.com"])
        self.assertEqual(fake_sdk.extract_calls[0]["urls"][0], "https://www.centene.com/")

    def test_tavily_client_prefers_registry_seed_urls_for_known_company(self):
        from account_intel.research_tools import TavilyResearchClient

        fake_sdk = FakeTavilySdk()
        client = TavilyResearchClient(api_key="test-key", sdk_client=fake_sdk, max_results=5)

        client.search_and_extract("Oscar Health", "hioscar.com", self._profile())

        extracted_urls = fake_sdk.extract_calls[0]["urls"]
        self.assertEqual(extracted_urls[0], "https://www.hioscar.com/about")
        self.assertIn("https://www.hioscar.com/plus-oscar", extracted_urls)
        self.assertIn("https://www.hioscar.com/careers/member-care", extracted_urls)

    def test_build_research_client_defaults_to_offline(self):
        from account_intel.research_tools import OfflineResearchClient, build_research_client

        with patch.dict(os.environ, {}, clear=True):
            client = build_research_client()

        self.assertIsInstance(client, OfflineResearchClient)

    def test_build_research_client_requires_tavily_key_for_tavily_mode(self):
        from account_intel.research_tools import build_research_client

        with self.assertRaises(ValueError):
            build_research_client(mode="tavily", api_key="")

    def test_classify_source_type_from_url(self):
        from account_intel.research_tools import classify_source_type

        self.assertEqual(classify_source_type("https://example.com/careers", "example.com"), "job_post")
        self.assertEqual(classify_source_type("https://example.com/news/launch", "example.com"), "news")
        self.assertEqual(classify_source_type("https://example.com/press/releases", "example.com"), "press_release")
        self.assertEqual(classify_source_type("https://example.com/about", "example.com"), "company_website")

    def test_candidate_findings_skip_page_headers_and_phone_numbers(self):
        from account_intel.research_tools import ResearchPage, pages_to_candidate_findings

        pages = [
            ResearchPage(
                url="https://www.hioscar.com/careers/member-care",
                source_type="job_post",
                text=(
                    "1-855-672-2788\n"
                    "Member Care at Oscar\n"
                    "We are rebuilding the health care system from the inside out with a team that puts people first. "
                    "See Member Care openings."
                ),
            )
        ]

        findings = pages_to_candidate_findings("Oscar Health", pages)

        self.assertEqual(len(findings), 1)
        self.assertNotIn("1-855", findings[0].claim)
        self.assertNotIn("Member Care at Oscar", findings[0].claim)
        self.assertIn("rebuilding the health care system", findings[0].claim)


if __name__ == "__main__":
    unittest.main()
