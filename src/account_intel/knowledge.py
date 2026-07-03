from __future__ import annotations

from pathlib import Path


KNOWLEDGE_FILES = (
    "approved_messaging.md",
    "product_positioning.md",
    "objection_handling.md",
)


def load_knowledge_snippets(directory: Path, max_characters: int = 1500) -> str:
    if not directory.exists() or not directory.is_dir():
        return ""
    chunks: list[str] = []
    for filename in KNOWLEDGE_FILES:
        path = directory / filename
        if path.exists() and path.is_file():
            chunks.append(path.read_text(encoding="utf-8").strip())
    combined = "\n\n".join(chunk for chunk in chunks if chunk)
    return combined[:max_characters]
