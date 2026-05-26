from __future__ import annotations

from pathlib import Path


def load_local_env(path: str | Path = ".env") -> bool:
    """Load local .env settings without replacing real environment variables."""
    env_path = Path(path)
    if not env_path.exists():
        return False
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install python-dotenv to load local .env files.") from exc
    return bool(load_dotenv(env_path, override=False))
