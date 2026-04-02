from __future__ import annotations

import json
from pathlib import Path

from signal_forge.pipeline import SignalForgePipeline


def main() -> None:
    pipeline = SignalForgePipeline(Path("outputs/audit.log.jsonl"))
    result = pipeline.run(
        {
            "macro": {
                "state": "bearish",
                "confidence": "high",
                "key_factors": ["growth is rolling over"],
                "time_horizon": "macro",
            },
            "geo": {
                "state": "neutral",
                "confidence": "medium",
                "key_factors": ["event premium contained"],
            },
            "market_quality": {
                "state": "bearish",
                "confidence": "medium",
                "key_factors": ["breadth is weak"],
            },
            "options": {
                "state": "bullish",
                "confidence": "high",
                "key_factors": ["short-term escape window is open"],
                "time_horizon": "intraday",
                "special_flags": {
                    "escape_window_state": "strong",
                    "iv_state": "expanding",
                },
            },
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
