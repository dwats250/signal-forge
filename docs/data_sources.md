# Signal Forge V2 — Data Sources

## Source Priority

```python
SYMBOL_SOURCE_PRIORITY = {
    "^VIX":     ["yfinance"],           # not available on Polygon
    "DX-Y.NYB": ["yfinance"],           # not available on Polygon
    "^TNX":     ["yfinance"],           # not available on Polygon
    "BTC-USD":  ["yfinance"],           # not available on Polygon
    "default":  ["yfinance", "polygon"] # equities: yfinance first, Polygon fallback
}
```

**VIX, DXY, TNX, and BTC are yfinance-only.** If yfinance fails for these, the system halts. There is no fallback.

---

## yfinance

### What It Fetches

**Live quotes** — `yf.Ticker(symbol).fast_info`:
- `fast_info.last_price` — current price
- `fast_info.previous_close` — prior session close
- pct_change computed as `(last_price - previous_close) / previous_close`
- `fast_info.regular_market_volume` — used for volume when available

`fast_info` is used instead of `Ticker.info` because `info` performs a full JSON scrape (~500ms); `fast_info` is a lightweight endpoint (~50–150ms).

**OHLCV history** — `yf.download(symbol, period="6mo", interval="1d")`:
- Returns ~126 trading days (6 calendar months)
- Used for EMA9, EMA21, EMA50, ATR14, momentum_5d, volume_ratio
- Fetched with `auto_adjust=True` (prices are split/dividend adjusted)
- Multi-index columns are flattened automatically

### Retry Behavior

```
Attempts: 3
Backoff:  2 seconds between attempts
Timeout:  10 seconds per request
```

On 3 consecutive failures: symbol marked `INVALID`, `failure_reason` logged, pipeline continues for non-halt symbols.

### Known yfinance Failure Modes

| Failure | Symptom | Fix |
|---|---|---|
| Market closed / extended hours | `fast_info.last_price` returns None | Expected — premarket data may be stale. Freshness check catches this. |
| Yahoo rate limiting | HTTPError 429 | Retry logic handles transient rate limits. Persistent: add sleep between symbols in `fetch_all()`. |
| Symbol not found | Empty DataFrame or KeyError in fast_info | Verify the ticker is correct. yfinance uses Yahoo Finance symbols (e.g. `DX-Y.NYB` not `DXY`). |
| Column MultiIndex on download | `KeyError: 'Close'` | Handled automatically by `if isinstance(df.columns, pd.MultiIndex)` flattening. |
| Weekend / holiday | Stale price returned from prior session | Freshness check (age_seconds < 300) will catch this for premarket runs. OHLCV cache is still valid. |

### yfinance Symbol Reference

| Symbol | Meaning | Notes |
|---|---|---|
| `^VIX` | CBOE Volatility Index | Caret prefix for indices |
| `DX-Y.NYB` | US Dollar Index (DXY) | Not `DXY` — that's a different product |
| `^TNX` | 10-Year Treasury Yield | In percentage points (4.31 = 4.31%) |
| `BTC-USD` | Bitcoin in USD | |
| `SPY`, `QQQ`, etc. | Standard equity tickers | |

---

## Polygon.io (Fallback)

### Coverage

Used for equity symbols only when yfinance fails. Never used for `^VIX`, `DX-Y.NYB`, `^TNX`, or `BTC-USD`.

**Endpoint:** `GET https://api.polygon.io/v2/aggs/ticker/{symbol}/prev`

Returns the previous trading day's OHLCV. This is **15-minute delayed** on the free tier — acceptable for premarket analysis where we're comparing against the prior session close.

### What pct_change Means from Polygon

Polygon's `prev` endpoint returns open (`o`) and close (`c`) for the prior day. pct_change is computed as `(close - open) / open`. This is intraday session return, not overnight gap. It differs slightly from yfinance's `(current - prev_close) / prev_close`. This is a known discrepancy; for regime voting thresholds (±0.3%) it's immaterial.

### Required Secrets

`POLYGON_API_KEY` must be set in GitHub Secrets (or `.env` locally). Without it, Polygon fallback silently skips and returns a failed quote:

```python
failure_reason = "POLYGON_API_KEY not set"
```

---

## OHLCV Cache

### Location and Naming

```
data/cache/{SAFE_SYMBOL}_ohlcv.parquet
```

Special characters in symbol names are replaced with underscores:
- `^VIX` → `_VIX_ohlcv.parquet`
- `DX-Y.NYB` → `DX-Y_NYB_ohlcv.parquet`
- `BTC-USD` → `BTC-USD_ohlcv.parquet`

### Staleness Rule

Cache is considered **stale** if the parquet file's modification time is older than 12 hours.

```python
_CACHE_STALE_HOURS = 12
```

On a normal weekday run at 13:00 UTC, the cache from the prior day (run at 13:00 UTC the day before) is exactly 24 hours old — always stale, always refetched. This is intentional: you always get fresh 6-month history on each premarket run.

### Fetch Period

```python
_OHLCV_PERIOD = "6mo"   # ~126 trading bars
```

**Why 6 months, not 30 days (the PRD default)?**

EMA convergence requires at minimum `3 × span` bars from a cold start:
- EMA9 needs ~27 bars (borderline with 30 days)
- EMA21 needs ~63 bars (fails with 30 days)
- EMA50 needs ~150 bars (marginally covered by 6mo)

With 30 days, EMA21 would have ~22% seed influence — enough to shift the value by several points relative to TradingView. 6 months brings seed influence below 1% for EMA21.

ATR is more sensitive to the seed value because Wilder's alpha (1/14 ≈ 0.071) is slower to converge. ~200 bars are needed for true seed-independence, but 126 bars gives ATR accuracy within ~5% of a fully-warmed reference — within the TradingView gate check tolerance.

### What Happens When Cache Fails

1. Cache hit fails (file corrupt, pyarrow missing): log warning, attempt fresh fetch
2. Fresh fetch fails: log error, return `None`
3. Symbol gets `sufficient_history = False` in `DerivedMetrics`
4. Structure engine returns `CHOP` for that symbol
5. Qualification rejects it — no trade output

The pipeline never estimates metrics from partial data.

### Clearing the Cache

```bash
rm data/cache/*.parquet
```

Next run will refetch all symbols from yfinance. Useful after:
- Extended market closure (holiday week)
- Suspected data corruption
- Testing derived metrics from scratch

---

## Freshness and Validation

### Age Checks (Layer 3)

| Check | Threshold | Effect |
|---|---|---|
| `age_seconds` | < 300s | Quote must be < 5 min old at validation time |
| `fetched_at_utc` absolute age | < 900s | Timestamp itself must be < 15 min ago |

Both checks are applied. A quote that was fetched 4 minutes ago but then sat in a slow pipeline for 6 minutes would fail the absolute timestamp check.

### Price Bounds (Layer 3)

```python
PRICE_BOUNDS = {
    "SPY": (300, 900),   "QQQ": (200, 900),   "IWM": (100, 450),
    "GLD": (100, 600),   "SLV": (10, 120),     "GDX": (15, 200),
    "PAAS": (5, 120),    "USO": (40, 250),     "XLE": (50, 180),
    "NVDA": (50, 2000),  "TSLA": (100, 600),   "AAPL": (120, 400),
    "META": (200, 1000), "AMZN": (100, 400),   "COIN": (50, 600),
    "MSTR": (100, 2000), "^VIX": (9, 90),      "^TNX": (1.0, 8.0),
    "DX-Y.NYB": (85, 125), "BTC-USD": (10000, 200000),
}
```

Bounds are sanity guards — they catch obviously wrong values, not market moves. Update them when the market moves a symbol significantly outside the range. The rule: bounds should be ~2–3× the observed range, not tight around current price.

---

## Debugging Data Issues

### Diagnosing a validation failure

```python
from signal_forge.ingestion import fetch_all
from signal_forge.normalization import normalize_all
from signal_forge.validation import validate_all

raw = fetch_all()
normed = normalize_all(raw)
results = validate_all(normed)

for r in results:
    if not r.passed:
        print(f"FAIL {r.symbol}: {r.failure_reason} | checks_failed={r.checks_failed}")
```

### Checking a single symbol manually

```python
from signal_forge.ingestion import fetch_quote
from signal_forge.normalization import normalize
from signal_forge.validation import validate

raw = fetch_quote("^VIX")
normed = normalize(raw)
result = validate(normed)
print(vars(result))
```

### Verifying OHLCV cache

```python
import pandas as pd
from pathlib import Path

df = pd.read_parquet("data/cache/SPY_ohlcv.parquet")
print(f"Rows: {len(df)}  Last: {df.index[-1]}  Cols: {list(df.columns)}")
print(df.tail(3))
```
