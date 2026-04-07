from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

try:
    from signal_forge.config import FMP_API_KEY
except ImportError:
    FMP_API_KEY = None

from signal_forge.env import load_repo_env


@dataclass
class FMPProvider:
    timeout_seconds: float = 5.0

    @property
    def name(self) -> str:
        return "fmp"

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], list[dict[str, str]]]:
        load_repo_env()
        api_key = os.getenv("FMP_API_KEY") or FMP_API_KEY
        if not api_key:
            return {}, [
                {
                    "provider": self.name,
                    "symbol": canonical,
                    "status": "failed",
                    "error_type": "MissingEnvVar",
                    "error": "FMP_API_KEY not configured",
                }
                for canonical in symbol_map
            ]

        histories: dict[str, list[float]] = {}
        diagnostics: list[dict[str, str]] = []
        for canonical, provider_symbol in symbol_map.items():
            url = (
                "https://financialmodelingprep.com/stable/historical-price-eod/full"
                f"?symbol={provider_symbol}&apikey={api_key}"
            )
            try:
                with urlopen(url, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                diagnostics.append(
                    {
                        "provider": self.name,
                        "symbol": canonical,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": f"HTTP {exc.code}",
                    }
                )
                continue
            except (OSError, TimeoutError, URLError, json.JSONDecodeError) as exc:
                diagnostics.append(
                    {
                        "provider": self.name,
                        "symbol": canonical,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue

            historical = self._extract_historical(payload)
            if not isinstance(historical, list):
                message = self._payload_error_message(payload)
                diagnostics.append(
                    {
                        "provider": self.name,
                        "symbol": canonical,
                        "status": "failed",
                        "error_type": "ProviderPayloadError",
                        "error": str(message),
                    }
                )
                continue

            closes = [
                float(day["close"])
                for day in reversed(historical[-10:])
                if isinstance(day, dict) and "close" in day
            ]
            if len(closes) >= 2:
                histories[canonical] = closes
                diagnostics.append(
                    {
                        "provider": self.name,
                        "symbol": canonical,
                        "status": "ok",
                        "count": str(len(closes)),
                    }
                )
                continue

            diagnostics.append(
                {
                    "provider": self.name,
                    "symbol": canonical,
                    "status": "failed",
                    "error_type": "PartialPayload",
                    "error": "fewer than 2 closes",
                }
            )

        return histories, diagnostics

    def _extract_historical(self, payload: object) -> list[dict[str, object]] | None:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            historical = payload.get("historical")
            return historical if isinstance(historical, list) else None
        return None

    def _payload_error_message(self, payload: object) -> str:
        if isinstance(payload, dict):
            return str(payload.get("Error Message") or payload.get("error") or "historical payload missing")
        if isinstance(payload, list):
            return "historical payload missing close data"
        return "historical payload missing"
