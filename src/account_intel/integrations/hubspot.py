from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HubSpotClient:
    token: str
    base_url: str = "https://api.hubapi.com"

    def create_note_payload(self, company_name: str, draft: dict[str, Any], source_urls: list[str]) -> dict[str, Any]:
        body = (
            f"AI-reviewed outreach draft for {company_name}\n\n"
            f"Subject: {draft['subject']}\n\n"
            f"{draft['body']}\n\n"
            "Sources:\n" + "\n".join(f"- {url}" for url in source_urls)
        )
        return {"properties": {"hs_timestamp": str(int(time.time() * 1000)), "hs_note_body": body}}

    def create_note(self, company_name: str, draft: dict[str, Any], source_urls: list[str]) -> str:
        payload = self.create_note_payload(company_name, draft, source_urls)
        request = urllib.request.Request(
            f"{self.base_url}/crm/v3/objects/notes",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec - user-provided token and official API
            raw = json.loads(response.read().decode("utf-8"))
        return str(raw.get("id", ""))
