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

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], list[dict[str, str]]]:
        try:
            raw = yf.download(
                tickers=list(symbol_map.values()),
                period=self.period,
                interval=self.interval,
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:
            return {}, [
                {
                    "provider": self.name,
                    "symbol": canonical,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                for canonical in symbol_map
            ]

        try:
            closes_frame = raw["Close"]
        except Exception as exc:
            return {}, [
                {
                    "provider": self.name,
                    "symbol": canonical,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": f"missing Close data: {exc}",
                }
                for canonical in symbol_map
            ]

        histories: dict[str, list[float]] = {}
        diagnostics: list[dict[str, str]] = []
        for canonical, provider_symbol in symbol_map.items():
            try:
                series = self._extract_close_series(closes_frame, provider_symbol)
            except Exception as exc:
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
            if len(series) >= 2:
                histories[canonical] = [float(value) for value in series]
                diagnostics.append(
                    {
                        "provider": self.name,
                        "symbol": canonical,
                        "status": "ok",
                        "count": str(len(series)),
                    }
                )
            else:
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

    def _extract_close_series(self, close_frame, provider_symbol: str):
        if hasattr(close_frame, "columns"):
            columns = getattr(close_frame, "columns", [])
            if len(columns) == 1:
                return close_frame.iloc[:, 0].dropna()
            if provider_symbol in columns:
                return close_frame[provider_symbol].dropna()
        return close_frame.dropna()
