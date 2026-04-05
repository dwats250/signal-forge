from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf


@dataclass
class YFinanceProvider:
    period: str = "10d"
    interval: str = "1d"

    @property
    def name(self) -> str:
        return "yfinance"

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], str | None]:
        try:
            raw = yf.download(
                tickers=list(symbol_map.values()),
                period=self.period,
                interval=self.interval,
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:
            return {}, str(exc)

        try:
            closes_frame = raw["Close"]
        except Exception as exc:
            return {}, f"missing Close data: {exc}"

        histories: dict[str, list[float]] = {}
        for canonical, provider_symbol in symbol_map.items():
            try:
                series = self._extract_close_series(closes_frame, provider_symbol)
            except Exception:
                continue
            if len(series) >= 2:
                histories[canonical] = [float(value) for value in series]

        return histories, None

    def _extract_close_series(self, close_frame, provider_symbol: str):
        if hasattr(close_frame, "columns"):
            columns = getattr(close_frame, "columns", [])
            if len(columns) == 1:
                return close_frame.iloc[:, 0].dropna()
            if provider_symbol in columns:
                return close_frame[provider_symbol].dropna()
        return close_frame.dropna()
