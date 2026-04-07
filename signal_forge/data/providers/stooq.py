from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen


@dataclass
class StooqProvider:
    timeout_seconds: float = 5.0

    @property
    def name(self) -> str:
        return "stooq"

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], list[dict[str, str]]]:
        histories: dict[str, list[float]] = {}
        diagnostics: list[dict[str, str]] = []
        for canonical, provider_symbol in symbol_map.items():
            url = f"https://stooq.com/q/d/l/?s={provider_symbol}&i=d"
            try:
                with urlopen(url, timeout=self.timeout_seconds) as response:
                    payload = response.read().decode("utf-8")
            except (OSError, TimeoutError, URLError) as exc:
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

            rows = list(csv.DictReader(io.StringIO(payload)))
            closes: list[float] = []
            for row in rows[-10:]:
                close = row.get("Close")
                if not close or close == "N/D":
                    continue
                try:
                    closes.append(float(close))
                except ValueError:
                    continue
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
                    "error_type": "EmptyPayload",
                    "error": "no usable closes",
                }
            )

        return histories, diagnostics
