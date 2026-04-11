# Signal Forge V2 — Architecture

## What This System Does

Signal Forge is a **macro-driven trade qualification engine**. It runs premarket, reads live market data, classifies the current regime, and either produces a small number of A+ setups or outputs nothing. The output is a decision filter, not a signal generator. Volume of output is not a success metric.

One sentence: **When it says trade → you trust it. When it says nothing → you stay flat.**

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  DATA SOURCES                                               │
│  yfinance (primary) ──────────────────────────────────────► │
│  Polygon.io free tier (fallback, equity symbols only)  ──►  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — RAW INGESTION          ingestion.py              │
│  Input:  symbol list (UNIVERSE, 20 symbols)                 │
│  Output: dict[str, RawQuote]                                │
│  Rule:   fetch only — no math, no transforms                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2 — NORMALIZATION          normalization.py          │
│  Input:  dict[str, RawQuote]                                │
│  Output: dict[str, NormalizedQuote]                         │
│  Rule:   pct_change → decimal, units annotated, UTC forced  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3 — VALIDATION GATE        validation.py             │
│  Input:  dict[str, NormalizedQuote]                         │
│  Output: list[ValidationResult]                             │
│  Rule:   hard pass/fail — no silent fallbacks               │
│  HALT:   any HALT_SYMBOL fails → PipelineHaltError raised   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
┌───────────────────────────┐  ┌──────────────────────────────┐
│  LAYER 4 — DERIVED        │  │  LAYER 5 — REGIME ENGINE     │
│  METRICS  derived.py      │  │  regime.py                   │
│  Input:  validated quotes │  │  Input:  validated quotes    │
│  Output: DerivedMetrics   │  │  Output: RegimeState         │
│  Rule:   EMA/ATR/momentum │  │  Rule:   8-input vote model  │
│  from parquet OHLCV cache │  │  HALT if tradeable=False:    │
│  Requires: ≥21 bars       │  │  skip Layers 6–8 entirely   │
└───────────────────────────┘  └──────────────────────────────┘
                    │                     │
                    └──────────┬──────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 6 — STRUCTURE ENGINE       structure.py              │
│  Input:  NormalizedQuotes + DerivedMetrics + RegimeState    │
│  Output: dict[str, StructureReading]                        │
│  Rule:   per-ticker classification; CHOP = disqualified     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 7 — TRADE QUALIFICATION    qualification.py          │
│  Input:  StructureReadings + DerivedMetrics + RegimeState   │
│  Output: list[QualificationResult]                          │
│  Rule:   9 sequential gates; TRADE | WATCHLIST | REJECTED   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 8 — OPTIONS EXPRESSION     options.py                │
│  Input:  TRADE-status QualificationResults                  │
│  Output: list[OptionsExpression]                            │
│  Rule:   direction × IV → strategy; ATR strikes; DTE range  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 9 — OUTPUT ENGINE          output.py                 │
│  Input:  OptionsExpressions + QualResults + RegimeState     │
│  Output: terminal report + reports/YYYY-MM-DD.md + Pushover │
│  Rule:   always writes — NO TRADE days still produce output │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 10 — AUDIT LOG             audit.py                  │
│  Input:  run metadata + all layer outputs                   │
│  Output: one JSON line appended to logs/audit.jsonl         │
│  Rule:   append-only, never overwritten                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Contracts

### Layer 1 → Layer 2: `RawQuote`

```python
@dataclass(frozen=True)
class RawQuote:
    symbol: str
    price: float                 # as-received from source
    pct_change_raw: float        # unit unknown — could be decimal or percent
    volume: Optional[float]
    fetched_at_utc: datetime
    source: str                  # "yfinance" | "polygon"
    fetch_succeeded: bool
    failure_reason: Optional[str]
```

### Layer 2 → Layer 3: `NormalizedQuote`

```python
@dataclass(frozen=True)
class NormalizedQuote:
    symbol: str
    price: float
    pct_change_decimal: float    # ALWAYS decimal — 5.2% is 0.052
    volume: Optional[float]
    fetched_at_utc: datetime     # UTC, tzinfo always set
    source: str
    units: str                   # "usd_price" | "index_level" | "yield_pct"
    age_seconds: float
```

Units by symbol:
- `^VIX` → `index_level` (e.g. 19.23)
- `DX-Y.NYB` → `index_level` (e.g. 98.70)
- `^TNX` → `yield_pct` (e.g. 4.32 — stored as-is, not converted)
- all others → `usd_price`

### Layer 3 → Layers 4–7: `ValidationResult`

```python
@dataclass(frozen=True)
class ValidationResult:
    symbol: str
    passed: bool
    quote: Optional[NormalizedQuote]   # None if failed
    failure_reason: Optional[str]
    checks_run: list[str]
    checks_failed: list[str]
```

### Layer 4: `DerivedMetrics`

```python
@dataclass(frozen=True)
class DerivedMetrics:
    symbol: str
    ema9: Optional[float]
    ema21: Optional[float]
    ema50: Optional[float]
    ema_aligned_bull: bool        # ema9 > ema21 > ema50
    ema_aligned_bear: bool        # ema9 < ema21 < ema50
    ema_spread_pct: Optional[float]   # (ema9 - ema21) / ema21
    atr14: Optional[float]        # Wilder's RMA, price units
    atr_pct: Optional[float]      # ATR / price
    momentum_5d: Optional[float]  # 5-day return, decimal
    volume_ratio: Optional[float] # today / 20d average
    iv_proxy: Optional[float]     # VIX level (equity symbols only)
    computed_at_utc: datetime
    sufficient_history: bool      # False if < 21 bars
```

### Layer 5: `RegimeState`

```python
@dataclass(frozen=True)
class RegimeState:
    regime: str             # RISK_ON | RISK_OFF | TRANSITION | CHAOTIC
    posture: str            # AGGRESSIVE_LONG | CONTROLLED_LONG | NEUTRAL_PREMIUM
                            # | DEFENSIVE_SHORT | STAY_FLAT
    confidence: float       # abs(net_score) / total_votes
    net_score: int          # sum of all votes
    total_votes: int        # number of inputs that cast a vote
    vote_breakdown: dict[str, int]
    vix_level: float
    vix_change: float
    tradeable: bool         # False when posture == STAY_FLAT or regime == CHAOTIC
    computed_at_utc: datetime
```

### Layer 6: `StructureReading`

```python
@dataclass(frozen=True)
class StructureReading:
    symbol: str
    classification: str    # TREND | PULLBACK | BREAKOUT | REVERSAL | CHOP
    ema_alignment: str     # "bull" | "bear" | "none"
    price_vs_ema21: str    # "above" | "below" | "unknown"
    price_vs_ema50: str    # "above" | "below" | "unknown"
    relative_strength: Optional[float]  # excess return vs SPY
    iv_environment: str    # LOW_IV | NORMAL_IV | ELEVATED_IV | HIGH_IV
    strategy_preference: str  # "debit" | "credit" | "either" | "defined_risk_reduced"
    disqualified: bool     # True when classification == CHOP
    computed_at_utc: datetime
```

### Layer 7: `QualificationResult`

```python
@dataclass(frozen=True)
class QualificationResult:
    symbol: str
    status: str                         # "TRADE" | "WATCHLIST" | "REJECTED"
    setup: Optional[CandidateSetup]
    gates_passed: list[str]
    gates_failed: list[str]
    watchlist_condition: Optional[str]  # if WATCHLIST: the one gate that failed
    rejection_reason: Optional[str]
```

### Layer 8: `OptionsExpression`

```python
@dataclass(frozen=True)
class OptionsExpression:
    symbol: str
    strategy: str          # "long_call_spread" | "bull_put_spread"
                           # | "long_put_spread" | "bear_call_spread"
    direction: str         # "long" | "short"
    iv_environment: str
    long_strike: float
    short_strike: float
    spread_width: float
    dte_min: int
    dte_max: int
    max_contracts: int
    max_risk_dollars: float
    exit_profit_target: str
    exit_loss: str
    size_reduced: bool     # True for HIGH_IV (50% size reduction)
    entry: float
    stop: float
    target: float
    structure: str
```

---

## Trust Boundary Rules

### Halt Symbols

If any of these fail validation, `PipelineHaltError` is raised and the entire pipeline aborts:

```
^VIX    DX-Y.NYB    ^TNX    SPY    QQQ
```

The output in this case is a `HALT` commit message and a terminal error. No markdown is written.

### Symbol Tiers

**Tier 1 — Required for pipeline to run:**
`^VIX`, `DX-Y.NYB`, `^TNX`, `BTC-USD`, `SPY`, `QQQ`

**Tier 2 — Optional; failure logged, pipeline continues:**
`IWM` and all equities/ETFs in the universe

**Non-tradeable — used for regime only, never qualified:**
`^VIX`, `DX-Y.NYB`, `^TNX`, `BTC-USD`

### Layer Skip Conditions

- If `regime.tradeable == False` → qualification produces all REJECTED at gate 1; no options expressions generated
- If `metrics.sufficient_history == False` → structure returns CHOP; symbol is disqualified
- If `atr14 is None` → stop cannot be defined; qualification rejects at gate 5

### Data Freshness Rules

| Check | Threshold | On failure |
|---|---|---|
| Quote age (premarket) | < 300 seconds | INVALID — excluded from pipeline |
| Absolute timestamp age | < 900 seconds | INVALID — excluded from pipeline |
| OHLCV cache staleness | < 12 hours | Refetch from yfinance |
| Minimum OHLCV bars | ≥ 21 bars | `sufficient_history = False` |

---

## File Map

```
signal_forge/
├── ingestion.py       Layer 1 — RawQuote, fetch_all(), UNIVERSE
├── normalization.py   Layer 2 — NormalizedQuote, normalize_all()
├── validation.py      Layer 3 — ValidationResult, validate_all(), PipelineHaltError
├── derived.py         Layer 4 — DerivedMetrics, compute_all(), fetch_ohlcv()
├── regime.py          Layer 5 — RegimeState, classify_regime(), from_validation_results()
├── structure.py       Layer 6 — StructureReading, classify_all()
├── qualification.py   Layer 7 — QualificationResult, qualify_all()
├── options.py         Layer 8 — OptionsExpression, express_all()
├── output.py          Layer 9 — render_terminal(), write_markdown(), send_pushover()
├── audit.py           Layer 10 — AuditRecord, write(), build_record()
├── run_premarket.py   Entry point — full L1–L10 orchestrator
└── run_intraday.py    Entry point — L1–L5 regime monitor only

data/cache/            OHLCV parquet files — {SYMBOL}_ohlcv.parquet
reports/               Daily markdown reports — YYYY-MM-DD.md
logs/
├── audit.jsonl        Append-only run records
└── intraday_state.json  Persisted regime state for dedup

.github/workflows/
└── signal_forge.yml   CI: premarket at 13:00 UTC + intraday every 30min 14–21 UTC
```
