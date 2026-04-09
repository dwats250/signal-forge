# FMP Access Consolidation + Duplicate Fetch Elimination (Phase 1, Strict Non-Regression)

## Objective

Reduce redundant FMP API calls and oversized FMP history pulls without materially reducing:

- normalized field coverage
- freshness quality
- fallback resilience
- rendered report consistency

This is a data acquisition stabilization pass only. It is not a trading-logic rewrite,
report redesign, or broad pipeline refactor.

---

## Primary Goal

Enforce one actual source-of-truth path for FMP-backed market data so downstream code
cannot lower call count cosmetically by:

- re-fetching fields after normalization
- reading or writing parallel caches
- creating separate fetch-service instances in the same run
- substituting stale or stub data more often than before

---

## Phase 1 Intent

Intentionally narrow and low-risk. Do only the minimum needed to:

- remove duplicate FMP fetch paths
- enforce one run-scoped fetch context
- preserve or improve fallback behavior on partial success
- reduce oversized history pulls where output equivalence is easy to verify
- add enough diagnostics to prove calls dropped without hidden regressions

No unrelated redesign is permitted.

---

## Current State (Baseline)

Before touching any code, capture a baseline FMP call log for the affected run types
(premarket report build, live pipeline execution). This is required for acceptance.

### Known FMP access paths (non-test, runtime)

| File | Line(s) | Description | Status |
|---|---|---|---|
| `signal_forge/data/providers/fmp.py` | 18–130 | `FMPProvider` — sole HTTP access class | Central, keep |
| `signal_forge/data/unified_data.py` | 76–196 | `UnifiedMarketDataClient` — designated central service | Central, keep |
| `signal_forge/data/live_fetch.py` | 123–179 | `collect_market_snapshot` — independent path, creates own `FMPProvider()` | Consolidate into `UnifiedMarketDataClient` consumer |
| `reports/morning_edge.py` | 460–461 | `_fetch_provider_entry("GOLD", FMPProvider(), "fmp")` — direct report-layer FMP instantiation | Blocking defect — remove |
| `reports/morning_edge.py` | 241 | `UnifiedMarketDataClient(providers=[provider])` inside `_fetch_provider_entry` | Blocking defect — remove with above |
| `signal_forge/data/live_fetch.py` | 83–112 | `debug_fetch()` — direct `requests.get` to `/api/v3/quote/SPY`, separate endpoint, no provider abstraction | Blocking defect — remove |

### Known parallel caches

| File | Function | Role | Status |
|---|---|---|---|
| `reports/morning_edge.py` | `load_market_data_cache()` (lines 457–470) | Tertiary fallback for GOLD and WTI, directly influences rendered commodity values | Must move into central service ownership |
| `signal_forge/data/unified_data.py` | `JsonDataCache` constructed inside `UnifiedMarketDataClient.__init__` | Currently per-instance, not run-scoped | Acceptable once per-instance dedup is enforced |

### Current lookback waste

`fmp.py` requests `/historical-price-eod/full` — full unbounded EOD history — but
extracts only the last 10 closes (`historical[-10:]`). The maximum number of closes
consumed downstream is 6 (index `-6` for `week_chg` in `_build_entries`). The target
lookback is **10 trading days** (matching the current extraction limit, while reducing
the HTTP payload from full history to a bounded window).

---

## Scope

### In Scope

- FMP-backed market data acquisition paths
- normalization handoff for FMP-backed fields
- same-run duplicate suppression
- run-scoped fetch context enforcement
- partial-batch and partial-success fallback behavior
- lookback minimization for FMP-backed requests
- lightweight fetch diagnostics
- removal of report-layer FMP re-fetches, report-layer FMP-backed field overrides, and
  report-owned FMP-backed caches
- audit and removal of non-test direct FMP access paths outside `UnifiedMarketDataClient`

### Out of Scope

- strategy, classification, scoring, or trading policy changes
- UI/UX or report styling changes
- broad redesign of non-FMP providers
- large persistence/cache infrastructure changes
- generalized telemetry platform work
- unrelated code cleanup for symmetry or aesthetics

---

## Problem Statement

The system is directionally centralized but not actually enforced. FMP-backed fields can
still be:

- fetched through multiple paths within one run
- re-fetched after upstream normalization (GOLD at `morning_edge.py:460`)
- overridden by report-layer logic reading a parallel cache (`load_market_data_cache`)
- hydrated from parallel caches outside the main acquisition path

Additional problems:

- `debug_fetch()` in `live_fetch.py` is a live direct HTTP call using `requests`, a
  different HTTP client, and a different FMP endpoint family than the rest of the codebase
- FMP requests pull unbounded full history per symbol; only 6–10 closes are used
- `live_fetch.py` and `unified_data.py` define an identical `HistoryProvider` Protocol
  independently and both instantiate `FMPProvider()` directly
- `fetch_entries` in `unified_data.py` treats any non-empty `histories` dict as batch
  success — symbols missing from the response are silently downgraded rather than
  continuing through the fallback chain

---

## Non-Goals / Do-Not-Do

- Do not lower calls by weakening qualitative output.
- Do not lower calls by reducing symbol coverage.
- Do not lower calls by serving stale or stub data more often under the same
  provider-success conditions.
- Do not redesign the whole pipeline.
- Do not rewrite unrelated providers just for consistency.
- Do not change report presentation except where required to remove data inconsistency
  caused by duplicate fetch paths.

---

## Requirements

### 1. Single Fetch Owner: `UnifiedMarketDataClient`

`UnifiedMarketDataClient` in `signal_forge/data/unified_data.py` is the designated
central fetch service.

- All FMP-backed data acquisition, normalization, retry, batching, and cache access must
  flow through `UnifiedMarketDataClient`.
- Downstream modules (including `live_fetch.py` consumers and `morning_edge.py`) may
  consume normalized outputs only.
- Downstream modules may not re-resolve, refresh, rewrite, replace, or override
  FMP-backed normalized fields using any direct provider, HTTP, or cache path.
- Any non-test runtime code path that performs direct FMP HTTP access or direct
  `FMPProvider` instantiation outside `UnifiedMarketDataClient` is a blocking defect for
  this phase.

Specific blocking defects to fix:

1. `reports/morning_edge.py:460` — `_fetch_provider_entry("GOLD", FMPProvider(), "fmp")`:
   delete `_fetch_provider_entry` and route GOLD resolution through the run-scoped client.
2. `reports/morning_edge.py:241` — `UnifiedMarketDataClient(providers=[provider])` inside
   `_fetch_provider_entry`: removed with the above.
3. `signal_forge/data/live_fetch.py:83–112` — `debug_fetch()`: delete entirely.
4. `signal_forge/data/live_fetch.py:124` — `providers = providers or [FMPProvider(), StooqProvider()]`
   in `collect_market_snapshot`: route through `UnifiedMarketDataClient` instead of
   instantiating providers directly.

### 2. Exactly One Run-Scoped Fetch Context Per Run

A run is one top-level invocation boundary:

- one CLI execution
- one scheduled report-build cycle
- one live pipeline execution

Exactly one `UnifiedMarketDataClient` instance must be created per run for FMP-backed
acquisition.

**Wiring mechanism:** constructor injection. The run entrypoint creates the client and
passes it explicitly to any downstream function that needs market data. Do not use a
module-level global or implicit singleton — these break test isolation.

Acceptable pattern:

```python
# entrypoint (morning_edge.py or pipeline.py)
client = UnifiedMarketDataClient()
market_data = fetch_market_data(client)
live_context = build_live_context(client)
```

Not acceptable:

```python
# deep in report code
client = UnifiedMarketDataClient()  # new instance, separate cache
```

### 3. No Parallel Caches for FMP-Backed Fields

- `load_market_data_cache()` in `morning_edge.py` currently acts as a tertiary fallback
  for GOLD and WTI commodity entries (lines 457–470), directly influencing rendered
  output. This logic must move into `UnifiedMarketDataClient`'s fallback chain.
- The file-backed `JsonDataCache` inside `UnifiedMarketDataClient` may remain as the
  stale-on-error fallback store, but it must be the only such store influencing
  FMP-backed field values.
- Report-local caches may remain only if they cannot influence FMP-backed normalized
  field values (e.g., purely for rendered HTML formatting).

### 4. Run-Scoped Duplicate Suppression

The single `UnifiedMarketDataClient` instance provides implicit within-run deduplication
via its `JsonDataCache`. No additional deduplication layer is required for Phase 1
provided the run-scoped instance is enforced.

Cache keys must include enough identity to prevent collisions:

- provider name
- canonical symbol set (sorted)
- endpoint family (e.g., `historical-price-eod`)
- lookback class (e.g., `10d`)

Do not include normalization schema version — this system has no schema versioning.

### 5. Partial-Batch and Partial-Success Fallback

The current `fetch_entries` in `unified_data.py` (lines 98–116) treats any non-empty
`histories` result as full batch success. Symbols absent from the batch response are
silently assigned a missing entry without attempting the next provider.

Fix: degrade per symbol, not per batch.

- After a provider response, iterate over the requested ticker set.
- For each ticker absent or malformed in the response, continue that ticker's fallback
  chain independently (try next provider, then cache, then stub).
- A batch response must not be treated as fully successful merely because transport
  succeeded or some symbols returned data.
- Partial-batch fallback must operate on the missing subset, not by reissuing the entire
  original request.

Cases to handle:

- symbol absent from response
- symbol present but `closes` list has fewer than 2 entries
- symbol present but payload is malformed or null
- symbol-level error in provider diagnostics

### 6. Lookback Minimization

**Current:** `fmp.py` requests `/historical-price-eod/full` — unbounded full history —
then extracts `historical[-10:]`.

**Target:** Request no more than **10 trading days** of EOD history per symbol.

Implementation: replace the `full` endpoint path with a date-bounded or limit-bounded
variant. The exact FMP parameter depends on the endpoint family used; prefer a `limit`
query parameter if the stable endpoint supports it, or a `from` date set 14 calendar
days prior to today to ensure 10 trading days are available.

Any lookback reduction must preserve current output behavior. `_build_entries` uses up
to index `-6` (week change) and `-10` (already the extraction limit). A 10-day lookback
preserves both.

### 7. Freshness Non-Regression

- Lower outbound call count must not be achieved by serving older cached data, stale-on-
  error data, or stub data more often under the same provider-success conditions.
- Normal same-run reuse within the single `UnifiedMarketDataClient` instance is allowed.
- Stale-on-error reuse is allowed only where equivalent fallback behavior already existed.
- For validated run types, no FMP-backed field that was live before this pass may become
  older, more stale, or more likely to come from fallback/stub under the same successful
  provider conditions.

### 8. Output Consistency

- `morning_edge.py` must not re-fetch individual FMP-backed fields after the
  `UnifiedMarketDataClient` call has already returned normalized data.
- GOLD and WTI commodity resolution must use the values returned by the run-scoped
  client, not a separate `_fetch_provider_entry` call and not `load_market_data_cache`
  as a parallel source.
- Related FMP-backed fields within a rendered artifact must come from the same
  centralized acquisition context.

### 9. Migration Guardrails

Treat all of the following as blocking defects for this phase:

- direct FMP HTTP calls outside `UnifiedMarketDataClient`
- direct `FMPProvider` instantiation outside `UnifiedMarketDataClient`
- report-owned caches that can populate or override FMP-backed normalized fields
- report-layer rewrites of FMP-backed fields sourced from fresh direct FMP calls
- multiple `UnifiedMarketDataClient` instances for FMP-backed work within one run
- the `debug_fetch()` function remaining in any non-test file

### 10. Lightweight Observability

Add diagnostics sufficient to validate improvement. Must be readable from standard
output or log output during a normal run (not a separate mode).

Required per validated run:

- total outbound FMP calls made
- duplicate-request suppression count (cache hits within run)
- partial-batch missing-symbol count
- fallback invocation count for missing symbols
- coverage before fallback and after fallback (symbol counts)
- stale/cache/stub usage count for FMP-backed fields
- lookback window requested (confirm bounded, not `full`)

Format: structured log lines are acceptable. Avoid logging so verbosely that failures
and fallback events are obscured.

---

## Implementation Guidance

### A. Baseline First

Before any code change:

1. Add temporary call-count logging to `FMPProvider.fetch_histories`.
2. Run the premarket report build and live pipeline.
3. Record: total calls, symbols per call, endpoint path, caller.
4. This baseline is required to verify the acceptance criterion "outbound FMP calls decrease."

### B. Centralize Access

1. Inventory every non-test `FMPProvider` instantiation (see Current State table above).
2. Delete `debug_fetch()` from `live_fetch.py`.
3. Refactor `collect_market_snapshot` in `live_fetch.py` to accept a
   `UnifiedMarketDataClient` parameter instead of instantiating providers directly.
4. Delete `_fetch_provider_entry` from `morning_edge.py` and route GOLD/WTI resolution
   through the run-scoped client's fallback chain.
5. Move `load_market_data_cache` tertiary-fallback logic for GOLD and WTI into
   `UnifiedMarketDataClient`'s fallback chain.

### C. Fix Partial-Batch Fallback

Refactor `fetch_entries` in `unified_data.py` so the outer loop iterates over providers
and the inner loop iterates over symbols, tracking which symbols are still pending. Only
advance a symbol out of the fallback chain when it has a valid result.

### D. Reduce Lookback

In `fmp.py`, replace the `full` endpoint path with a bounded request. Confirm that the
10-close extraction in `_extract_historical` / `historical[-10:]` still works correctly
after the change.

### E. Preserve Existing Fallback Intent

- Do not remove fallback behavior merely to reduce call count.
- Do not expand stale/cache/stub usage in a way that weakens live behavior.

### F. Minimize Change Surface

- Prefer targeted edits over full rewrites.
- Keep `UnifiedMarketDataClient`'s public interface stable where practical.
- The `HistoryProvider` Protocol in `live_fetch.py` is a duplicate of the one in
  `unified_data.py` — consolidate to one definition, but only if it does not require
  touching unrelated call sites.

---

## Deliverables

1. Baseline call log captured before any changes (see Implementation Guidance A)
2. One enforced central fetch path: `UnifiedMarketDataClient` is the sole FMP access point
3. One run-scoped `UnifiedMarketDataClient` instance per run, injected via constructors
4. `debug_fetch()` removed from `live_fetch.py`
5. `_fetch_provider_entry` and its `FMPProvider()` instantiation removed from `morning_edge.py`
6. `collect_market_snapshot` in `live_fetch.py` refactored to consume `UnifiedMarketDataClient`
7. `load_market_data_cache` tertiary fallback for GOLD/WTI moved into central service
8. Per-symbol fallback behavior for partial batch/partial success cases in `fetch_entries`
9. FMP lookback reduced from `full` history to 10 trading days
10. Diagnostics per run: call count, cache hits, fallback usage, partial-batch handling, coverage
11. Explicit list of any remaining non-test bypass paths not fixed, if any remain

---

## Acceptance Criteria

Implementation is complete only if all conditions below are true.

### 1. Baseline Established

- A pre-change call log exists showing outbound FMP call count for the validated run types.

### 2. Duplicate Fetch Control

- Outbound FMP calls decrease for the validated run types compared to the baseline.
- The decrease is not achieved by increased cache age, increased stale/cache/stub usage,
  or reduced field/symbol coverage.

### 3. Single Fetch Context Enforcement

- For each validated run type, all FMP-backed consumers use the same `UnifiedMarketDataClient`
  instance.
- No separate in-run `UnifiedMarketDataClient` instances remain for FMP-backed work.

### 4. No Bypass Paths

- Repo search shows no non-test `FMPProvider()` instantiations outside `UnifiedMarketDataClient`.
- Repo search shows no non-test direct FMP HTTP calls (including `requests.get` or
  `urlopen` calls to `financialmodelingprep.com`) outside `FMPProvider`.
- `debug_fetch()` does not exist in any non-test file.
- `_fetch_provider_entry` does not exist in `morning_edge.py` or any report file.
- `load_market_data_cache` is not used as a source for FMP-backed normalized field values
  outside the central service.

### 5. Coverage Preservation

- Field-level and symbol-level coverage for validated run types is unchanged under the
  same provider-success conditions.
- Missing symbols from partial batch success continue through fallback rather than being
  dropped immediately.

### 6. Freshness Non-Regression

- For validated run types, no FMP-backed field that was live before this pass is now
  served from an older cache or stub under the same successful provider conditions.
- Lower call count does not come primarily from stale reuse.

### 7. Fallback Non-Regression

- Fallback/stub usage rate for validated run types does not increase under the same
  provider-success conditions.
- Partial-batch handling is validated for:
  - symbols absent from the response
  - symbols present with fewer than 2 closes
  - malformed or null per-symbol payloads
  - per-symbol error entries in provider diagnostics

### 8. Output Parity

- Rendered report outputs remain materially consistent with prior behavior except where
  the change clearly improves correctness by removing inconsistent downstream overrides.
- No critical field is silently removed or downgraded to save calls.

### 9. Output Consistency

- No report/build/render path overwrites an already-normalized FMP-backed field from
  another path.
- GOLD and WTI commodity values in a rendered artifact come from the run-scoped
  `UnifiedMarketDataClient`, not from a separate provider call or parallel cache.

### 10. Lookback Improvement

- FMP requests no longer use the `full` unbounded history endpoint.
- Requests are bounded to 10 trading days (or equivalent date range).
- `_build_entries` output for `day_chg` and `week_chg` is unchanged for validated run types.

### 11. Verifiable Diagnostics

Per validated run, the following are readable from standard output or logs:

- total outbound FMP calls
- cache hit count (within-run deduplication)
- partial-batch missing-symbol count
- fallback invocation count for missing symbols
- symbol coverage before and after fallback
- stale/cache/stub usage count
- lookback window used (confirming bounded request)

---

## Validation Plan

Validate against the primary run types affected by current duplicate behavior:

- premarket report build (`python -m reports.morning_edge` or `build_all.py`)
- live pipeline execution (`signal_forge/data/live_fetch.py` path)
- any combined build path that exercises repeated semantic requests in one invocation

### For each run type, demonstrate:

- fewer outbound FMP calls than the captured baseline
- unchanged or improved symbol/field coverage
- no increased stale/cache/stub reliance under successful provider conditions
- no `_fetch_provider_entry` or `FMPProvider()` call outside `UnifiedMarketDataClient`
- GOLD and WTI resolve correctly without a report-layer FMP re-fetch
- unchanged or intentionally improved rendered outputs

---

## Files to Review First

- `signal_forge/data/unified_data.py` — designated central service; needs per-symbol fallback fix
- `signal_forge/data/providers/fmp.py` — lookback change goes here
- `signal_forge/data/live_fetch.py` — `collect_market_snapshot` refactor + `debug_fetch` removal
- `signal_forge/data/cache.py` — verify `JsonDataCache` is not instantiated outside the central service
- `reports/morning_edge.py` — `_fetch_provider_entry` removal, `load_market_data_cache` tertiary-fallback migration, run-scoped client injection
- `reports/build_all.py` — verify no FMP access paths introduced at the build layer
