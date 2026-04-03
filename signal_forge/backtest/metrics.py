from __future__ import annotations


def calculate_metrics(trade_results: list[dict[str, float | int | str]]) -> dict[str, float]:
    closed = [result for result in trade_results if result.get("outcome") != "no_data"]
    if not closed:
        return {
            "win_rate": 0.0,
            "average_r_multiple": 0.0,
            "max_drawdown": 0.0,
            "total_return": 0.0,
        }

    wins = sum(1 for result in closed if result["outcome"] == "win")
    total_return = round(sum(float(result["pnl"]) for result in closed), 4)
    average_r = round(
        sum(float(result["r_multiple"]) for result in closed) / len(closed),
        4,
    )

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for result in closed:
        equity += float(result["pnl"])
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    return {
        "win_rate": round(wins / len(closed), 4),
        "average_r_multiple": average_r,
        "max_drawdown": round(abs(max_drawdown), 4),
        "total_return": total_return,
    }

