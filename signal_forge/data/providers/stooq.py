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

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], str | None]:
        histories: dict[str, list[float]] = {}
        for canonical, provider_symbol in symbol_map.items():
            url = f"https://stooq.com/q/d/l/?s={provider_symbol}&i=d"
            try:
                with urlopen(url, timeout=self.timeout_seconds) as response:
                    payload = response.read().decode("utf-8")
            except (OSError, TimeoutError, URLError) as exc:
                return {}, str(exc)

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
            if closes:
                histories[canonical] = closes

        return histories, None
