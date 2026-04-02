# Agents

## Purpose

Signal Forge uses domain agents to turn market context into structured inputs for classification, thesis construction, and trading decision support.

Agents operate within the canonical pipeline:

Inputs
-> Normalization
-> Reading Construction
-> Classification
-> Scoring
-> Context Filters
-> Output
-> Logging / Validation

Current agents provide domain readings and structured judgments. They do not replace scoring, context filters, or operator review.

## Agent Rules

- each agent owns one domain
- each agent produces explicit, reviewable output
- agents do not reinterpret another domain's logic
- agents support decision-making, not opaque automation

## Current Agent Set

### Macro

Purpose:
Interpret macro conditions into directional regime context.

Inputs:
- rates
- inflation
- growth
- liquidity
- cross-asset confirmation

Outputs:
- macro state
- confidence
- key factors
- time horizon

### Geopolitical

Purpose:
Translate geopolitical stress into market-relevant risk posture.

Inputs:
- event severity
- regional exposure
- commodity sensitivity
- transmission channels

Outputs:
- geopolitical state
- confidence
- key factors
- event flags

### Market Quality

Purpose:
Judge tape health, participation quality, and tradability.

Inputs:
- breadth
- internals
- liquidity
- volume quality
- correlation behavior

Outputs:
- market quality state
- confidence
- key factors
- structural flags

### Options Behavior

Purpose:
Interpret volatility behavior, convexity, and positioning context.

Inputs:
- implied volatility
- skew
- term structure
- positioning proxies
- flow context

Outputs:
- options state
- confidence
- key factors
- volatility and escape-window flags

### Dislocation Inputs

Purpose:
Provide the paired futures and ETF moves used by dislocation classification.

Inputs:
- futures symbol
- ETF symbol
- pair-level percentage moves

Outputs:
- normalized dislocation reading

## Current Boundaries

- agents provide structured inputs and domain judgments
- dislocation classification converts pair readings into explicit signal labels
- thesis construction combines domain outputs into a system view
- conflict handling applies deployment constraints
- execution output remains downstream of interpretation

## Current Status

Implemented now:
- stub agents for macro, geopolitical, market quality, and options behavior
- a stub dislocation fetcher for pair-level input

Planned next:
- tighter normalization boundaries
- dedicated scoring
- formal context filtering
- stronger operator-facing output
