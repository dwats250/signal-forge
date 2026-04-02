"""Minimal adapter for OpenWolf memory layer."""

from pathlib import Path

_WOLF_DIR = Path(__file__).resolve().parents[2] / ".wolf"
_CEREBRUM = _WOLF_DIR / "cerebrum.md"


def store_context(text: str) -> None:
    try:
        with _CEREBRUM.open("a", encoding="utf-8") as f:
            f.write(f"\n{text}\n")
    except FileNotFoundError:
        pass


def retrieve_context(query: str) -> str:
    try:
        content = _CEREBRUM.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    if not query:
        return content
    lines = [line for line in content.splitlines() if query.lower() in line.lower()]
    return "\n".join(lines)
