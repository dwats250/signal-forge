from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import urlopen


def load_price_series(symbol: str) -> list[float]:
    symbol = symbol.upper().strip()
    if not symbol:
        raise ValueError("symbol must not be empty")

    api_key = os.getenv("FMP_API_KEY")
    if api_key:
        remote = _load_from_fmp(symbol, api_key)
        if remote:
            return remote

    return _mock_series(symbol)


def _load_from_fmp(symbol: str, api_key: str) -> list[float]:
    url = (
        "https://financialmodelingprep.com/stable/historical-price-eod/full"
        f"?symbol={symbol}&apikey={api_key}"
    )
    try:
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, URLError, json.JSONDecodeError):
        return []

    historical = payload.get("historical")
    if not isinstance(historical, list):
        return []

    closes = [
        float(day["close"])
        for day in reversed(historical[-30:])
        if isinstance(day, dict) and "close" in day
    ]
    return closes


def _mock_series(symbol: str) -> list[float]:
    seed = sum(ord(char) for char in symbol)
    base = 90 + (seed % 20)
    path = [float(base)]
    for index in range(1, 8):
        shift = ((seed + index) % 5) - 1
        path.append(round(path[-1] + shift, 2))
    return path

