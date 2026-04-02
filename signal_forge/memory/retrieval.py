from __future__ import annotations

from signal_forge.memory.openwolf_adapter import retrieve_context


def find_similar_context(symbol: str, signal: str) -> str:
    query = f"{symbol} {signal}"
    return retrieve_context(query)
