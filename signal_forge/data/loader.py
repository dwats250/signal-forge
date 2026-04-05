from __future__ import annotations

from signal_forge.data.unified_data import UnifiedMarketDataClient


def load_price_series(symbol: str) -> list[float]:
    symbol = symbol.upper().strip()
    if not symbol:
        raise ValueError("symbol must not be empty")

    client = UnifiedMarketDataClient()
    return client.fetch_series(symbol, fallback_builder=_mock_series)


def _mock_series(symbol: str) -> list[float]:
    seed = sum(ord(char) for char in symbol)
    base = 90 + (seed % 20)
    path = [float(base)]
    for index in range(1, 8):
        shift = ((seed + index) % 5) - 1
        path.append(round(path[-1] + shift, 2))
    return path
