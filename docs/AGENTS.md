# Agents

## Macro Regime

- Name: Macro Regime
- Purpose: Interpret macro conditions into regime judgment and directional context.
- Inputs: Rates, inflation, growth, liquidity, cross-asset confirmation.
- Outputs: Regime state, pressure summary, confidence, invalidation conditions.
- Ownership boundaries: Owns macro interpretation only and does not price geopolitical, market microstructure, or options behavior.

## Geopolitical Premium

- Name: Geopolitical Premium
- Purpose: Translate geopolitical stress into market-relevant premium and risk posture.
- Inputs: Event severity, regional exposure, commodity sensitivity, risk transmission channels.
- Outputs: Premium state, stress narrative, scenario flags, decay expectations.
- Ownership boundaries: Owns geopolitical interpretation only and does not override macro or execution logic.

## Market Quality

- Name: Market Quality
- Purpose: Judge tape health, participation quality, and structural stability.
- Inputs: Breadth, internals, volume quality, correlation behavior, liquidity conditions.
- Outputs: Quality score, participation regime, fragility flags, confirmation state.
- Ownership boundaries: Owns market structure interpretation only and does not assign options views or execution tactics.

## Options Behavior

- Name: Options Behavior
- Purpose: Interpret nonlinear positioning, volatility behavior, and convexity implications.
- Inputs: Implied volatility, skew, term structure, dealer positioning proxies, flow context.
- Outputs: Volatility regime, convexity risk, opportunity windows, options-specific warnings.
- Ownership boundaries: Owns options interpretation only and protects nonlinear logic from simplification by other domains.

## Execution

- Name: Execution
- Purpose: Convert thesis state into actionable posture, trade framing, and risk constraints.
- Inputs: Unified thesis state, operator constraints, instrument selection rules, risk budget.
- Outputs: Execution posture, candidate structures, timing guidance, invalidation mapping.
- Ownership boundaries: Consumes upstream interpretation and does not reinterpret domain signals.

## Learning

- Name: Learning
- Purpose: Record decision quality, outcome context, and reviewable improvement signals.
- Inputs: Thesis snapshots, execution records, outcomes, operator review notes.
- Outputs: Audit trails, pattern summaries, review prompts, learning candidates.
- Ownership boundaries: Produces auditable feedback only and does not mutate live decision logic automatically.
