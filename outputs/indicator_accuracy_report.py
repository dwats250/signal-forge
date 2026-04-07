from __future__ import annotations


def render_indicator_accuracy_report(summary: dict[str, object]) -> str:
    total = int(summary.get("total_signals", 0))
    accuracy = _pct(summary.get("overall_directional_accuracy"))
    follow = _pct(summary.get("strong_follow_through_rate"))
    failure = _pct(summary.get("immediate_failure_rate"))
    classification = str(summary.get("indicator_classification", "NOISY"))
    by_ticker = summary.get("by_ticker", {})

    best_ticker = _best_ticker(by_ticker, reverse=True)
    worst_ticker = _best_ticker(by_ticker, reverse=False)

    lines = [
        "## SUMMARY",
        f"- total signals: {total}",
        f"- overall directional accuracy: {accuracy}",
        f"- strong follow-through rate: {follow}",
        f"- immediate failure rate: {failure}",
        f"- best ticker: {best_ticker}",
        f"- worst ticker: {worst_ticker}",
        f"- classification: {classification}",
        f"- verdict: {_verdict_line(classification, total)}",
        "",
        "## PER TICKER",
    ]

    if not isinstance(by_ticker, dict) or not by_ticker:
        lines.append("- no per-ticker results available")
        return "\n".join(lines)

    for ticker in sorted(by_ticker):
        metrics = by_ticker[ticker]
        lines.append(
            f"- {ticker}: signals={metrics.get('total_signals', 0)} "
            f"accuracy={_pct(metrics.get('overall_directional_accuracy'))} "
            f"follow={_pct(metrics.get('strong_follow_through_rate'))} "
            f"fail={_pct(metrics.get('immediate_failure_rate'))}"
        )
    return "\n".join(lines)


def _best_ticker(by_ticker: object, *, reverse: bool) -> str:
    if not isinstance(by_ticker, dict) or not by_ticker:
        return "n/a"
    ranked = sorted(
        by_ticker.items(),
        key=lambda item: (
            float(item[1].get("overall_directional_accuracy", 0.0)),
            float(item[1].get("strong_follow_through_rate", 0.0)),
            -float(item[1].get("immediate_failure_rate", 0.0)),
        ),
        reverse=reverse,
    )
    return str(ranked[0][0])


def _pct(value: object) -> str:
    return f"{float(value or 0.0) * 100:.1f}%"


def _verdict_line(classification: str, total: int) -> str:
    if total == 0:
        return "No validated signals yet; harness is ready but the adapter/data path still needs signals."
    if classification == "USEFUL":
        return "Indicator appears usable without claiming parameter-level certainty."
    if classification == "MIXED":
        return "Indicator shows selective value and likely needs filtering review later."
    return "Indicator currently looks noisy relative to the configured outcome thresholds."
