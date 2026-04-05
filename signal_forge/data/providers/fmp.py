from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen


@dataclass
class FMPProvider:
    timeout_seconds: float = 5.0

    @property
    def name(self) -> str:
        return "fmp"

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], str | None]:
        api_key = os.getenv("FMP_API_KEY")
        if not api_key:
            return {}, "FMP_API_KEY not configured"

        histories: dict[str, list[float]] = {}
        for canonical, provider_symbol in symbol_map.items():
            url = (
                "https://financialmodelingprep.com/stable/historical-price-eod/full"
                f"?symbol={provider_symbol}&apikey={api_key}"
            )
            try:
                with urlopen(url, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (OSError, TimeoutError, URLError, json.JSONDecodeError) as exc:
                return {}, str(exc)

            historical = payload.get("historical")
            if not isinstance(historical, list):
                continue

            closes = [
                float(day["close"])
                for day in reversed(historical[-10:])
                if isinstance(day, dict) and "close" in day
            ]
            if closes:
                histories[canonical] = closes

        return histories, None
