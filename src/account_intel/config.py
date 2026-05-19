from __future__ import annotations

from pathlib import Path

import yaml

from account_intel.models import ICPProfile


def load_icp_profiles(path: Path) -> dict[str, ICPProfile]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    profiles: dict[str, ICPProfile] = {}
    for key, item in raw["profiles"].items():
        profiles[key] = ICPProfile(
            key=key,
            name=item["name"],
            description=item["description"],
            target_segments=list(item["target_segments"]),
            pain_points=list(item["pain_points"]),
            buying_signals=list(item["buying_signals"]),
            disqualifiers=list(item["disqualifiers"]),
            approved_outreach_angles=list(item["approved_outreach_angles"]),
            risk_notes=list(item["risk_notes"]),
        )
    return profiles
