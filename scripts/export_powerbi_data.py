from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from account_intel.env import load_local_env
from account_intel.powerbi_export import export_powerbi_snapshot


def main() -> None:
    load_local_env(ROOT / ".env")
    base_url = os.getenv(
        "ACCOUNT_INTEL_BASE_URL", "https://account-intel-outreach.onrender.com"
    )
    api_key = os.getenv("ACCOUNT_INTEL_API_KEY", "")
    output_dir = ROOT / "powerbi" / "data"
    manifest = export_powerbi_snapshot(base_url, api_key, output_dir)
    print(f"powerbi_snapshot={output_dir}")
    print(f"views={manifest['views']}")


if __name__ == "__main__":
    main()
