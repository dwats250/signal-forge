# Architecture

## System Flow

Data Layer
-> Feature Normalization
-> Interpretive Agents
-> Unified Thesis State
-> Execution
-> Surface Layer
-> Learning

## Domain Model

- Data Layer gathers market, macro, geopolitical, and options inputs.
- Feature Normalization standardizes timestamps, units, and derived features before interpretation.
- Interpretive Agents each own one domain judgment path.
- Unified Thesis State collects domain outputs into a reviewable system thesis.
- Execution consumes thesis state and emits actions without reinterpreting upstream logic.
- Surface Layer renders reports, dashboards, and operator review artifacts.
- Learning records outcomes, review notes, and decision quality for later analysis.

## Key Rule

No signal is interpreted by multiple domains independently.

## Boundary Implications

- Domain ownership must be singular and explicit.
- Shared data may exist, but shared interpretation may not.
- Cross-domain coordination happens through the unified thesis state, not side-channel logic.
