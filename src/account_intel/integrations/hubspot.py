from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

RequestJson = Callable[[str, str, str, dict[str, Any] | None, int], dict[str, Any]]


def _request_json(
    url: str,
    token: str,
    method: str,
    payload: dict[str, Any] | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for attempt in range(3):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
                body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt < 2:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(min(delay, 5))
                continue
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HubSpot request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < 2:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"HubSpot request failed: {exc.reason}") from exc
    raise RuntimeError("HubSpot request failed after retries.")


@dataclass(frozen=True)
class HubSpotClient:
    token: str
    base_url: str = "https://api.hubapi.com"
    request_json: RequestJson = field(default=_request_json, repr=False, compare=False)

    def find_or_create_company(self, company_name: str, domain: str | None) -> str:
        search_property = "domain" if domain else "name"
        search_value = domain or company_name
        search_payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": search_property,
                            "operator": "EQ",
                            "value": search_value,
                        }
                    ]
                }
            ],
            "properties": ["name", "domain"],
            "limit": 1,
        }
        search_result = self._request("POST", "/crm/v3/objects/companies/search", search_payload)
        matches = search_result.get("results") or []
        if matches:
            return str(matches[0]["id"])

        properties = {"name": company_name}
        if domain:
            properties["domain"] = domain
        created = self._request("POST", "/crm/v3/objects/companies", {"properties": properties})
        company_id = str(created.get("id") or "")
        if not company_id:
            raise RuntimeError("HubSpot company creation returned no record ID.")
        return company_id

    def create_note_payload(
        self,
        company_name: str,
        draft: dict[str, Any],
        source_urls: list[str],
        company_id: str | None = None,
    ) -> dict[str, Any]:
        body = (
            f"AI-reviewed outreach draft for {company_name}\n\n"
            f"Subject: {draft['subject']}\n\n"
            f"{draft['body']}\n\n"
            "Sources:\n" + "\n".join(f"- {url}" for url in source_urls)
        )
        payload: dict[str, Any] = {
            "properties": {
                "hs_timestamp": str(int(time.time() * 1000)),
                "hs_note_body": body,
            }
        }
        if company_id:
            payload["associations"] = [
                {
                    "to": {"id": company_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 190,
                        }
                    ],
                }
            ]
        return payload

    def create_note(self, company_name: str, draft: dict[str, Any], source_urls: list[str]) -> str:
        company_id = self.find_or_create_company(company_name, draft.get("company_domain"))
        payload = self.create_note_payload(company_name, draft, source_urls, company_id=company_id)
        created = self._request("POST", "/crm/v3/objects/notes", payload)
        note_id = str(created.get("id") or "")
        if not note_id:
            raise RuntimeError("HubSpot note creation returned no record ID.")
        return note_id

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout_seconds: int = 20,
    ) -> dict[str, Any]:
        return self.request_json(
            f"{self.base_url}{path}",
            self.token,
            method,
            payload,
            timeout_seconds,
        )
