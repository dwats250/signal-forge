# Architecture Refinements Review

Status: Review Draft  
Purpose: Candidate intelligence layer review and scope classification

## Review Standard

A refinement moves into Core v1 only if it:

1. meaningfully improves decision quality
2. captures a real blind spot in current trading behavior
3. does not duplicate an existing domain
4. can be expressed with clear ownership, inputs, and outputs

## Decision Summary

- Instrument Intelligence: Deferred
- Opportunity Detection: Deferred
- Expression Quality: Deferred, highest priority next
- Exit Intelligence: Deferred
- Trade State Awareness: Deferred
- Surface-Layer Visual Intelligence: Deferred

No refinement should be elevated into Core v1 at this stage.

Reason:
The current v1 architecture is still defining the contract for domain outputs, thesis synthesis, conflict resolution, and execution constraints. These refinements are real and valuable, but most sit downstream of the current contract boundary or require additional object models that do not yet exist in the minimal build.

## 1. Instrument Intelligence

### Decision

Deferred

### Why

This captures a real blind spot: names are not interchangeable, and expression quality is partly instrument-specific. However, it is not yet cleanly separated from two adjacent concerns:

- live Options Behavior
- later Expression Quality

Without a clear distinction between baseline instrument profile and current-state options conditions, this will drift into a loose personality layer.

### Review Rule Assessment

- Improves decision quality: yes
- Captures a real blind spot: yes
- Duplicates an existing domain: partially, unless baseline vs current-state boundaries are formalized
- Clear ownership: not fully stable yet

### Recommendation

Keep out of Core v1. Revisit after Expression Quality is specified, because Instrument Intelligence likely becomes a supporting reference layer rather than a first-class v1 domain.

## 2. Opportunity Detection

### Decision

Deferred

### Why

This is valuable, but it is not part of the minimum reasoning contract. The current architecture already allows tactical conditions to exist through Options Behavior and the Conflict Rules Engine. What is missing is a dedicated way to surface and rank those openings.

That makes this important, but not core for first implementation.

### Review Rule Assessment

- Improves decision quality: yes
- Captures a real blind spot: yes
- Duplicates an existing domain: risks overlap with Options Behavior and Conflict Rules if not narrowly scoped
- Clear ownership: mostly yes, under Options Behavior

### Recommendation

Treat this as a v1.5 refinement once the core thesis and conflict outputs are stable enough to expose “permission” separately from “opportunity”.

## 3. Expression Quality

### Decision

Deferred, highest-priority next formal PRD

### Why

This is the strongest refinement because it captures a genuine blind spot between “valid thesis” and “valid trade expression.” That distinction is central to actual trading performance and is not fully owned today by any existing domain.

It does not duplicate Macro, Geo, or Market Quality.
It only partially overlaps with Options Behavior, and that overlap can be resolved cleanly:

- Options Behavior owns current nonlinear market state
- Expression Quality owns how cleanly a specific instrument or chain can express the thesis

This is the clearest bridge between architecture and actual execution quality.

### Review Rule Assessment

- Improves decision quality: yes, materially
- Captures a real blind spot: yes
- Duplicates an existing domain: no, if boundary is defined correctly
- Clear ownership: yes, as a dedicated submodule adjacent to options and consumed by Execution

### Recommendation

Do not force it into Core v1 now, but make it the next architecture PRD.

## 4. Exit Intelligence

### Decision

Deferred

### Why

The idea is valid and tightly connected to how losses are reduced and tactical profits are realized. The problem is architectural timing: it requires active trade-state context, realized path tracking, and position-aware logic that the current v1 system does not yet model.

This is not a reason to reject it. It is a reason to stage it after the first execution and review contracts exist.

### Review Rule Assessment

- Improves decision quality: yes
- Captures a real blind spot: yes
- Duplicates an existing domain: no
- Clear ownership: partially, but depends on trade-state objects that do not exist yet

### Recommendation

Keep deferred, but note that it is strategically important and should follow soon after the first minimal build proves the thesis-to-execution contract.

## 5. Trade State Awareness

### Decision

Deferred

### Why

This is a real concept, but it is explicitly post-entry and stateful. Core v1 is still about generating a reviewable thesis and execution posture before execution. Introducing trade-state awareness now would blur the boundary between architecture and position management.

### Review Rule Assessment

- Improves decision quality: yes
- Captures a real blind spot: yes
- Duplicates an existing domain: no
- Clear ownership: only partially, because it spans Execution and Learning

### Recommendation

Defer until after the initial execution contract exists and active-position context is modeled explicitly.

## 6. Surface-Layer Visual Intelligence

### Decision

Deferred

### Why

This is valuable for cognition, but it is downstream of backend contract stability. The main risk here is not conceptual weakness. The risk is frontend logic invention before backend fields are frozen.

### Review Rule Assessment

- Improves decision quality: indirectly
- Captures a real blind spot: yes, in operator cognition
- Duplicates an existing domain: no
- Clear ownership: yes, Surface Layer

### Recommendation

Keep it out of Core v1 backend scope. Prototype only after thesis, conflict, and expression-related contracts stabilize.

## 7. Answers To Immediate Review Questions

### 1. Which refinements capture true blind spots rather than nice-to-have ideas?

The strongest blind spots are:

- Expression Quality
- Exit Intelligence
- Instrument Intelligence

These reflect real trading failure modes:

- a correct thesis expressed through a poor chain
- a wrong thesis temporarily offering a recoverable exit
- different instruments behaving in meaningfully different ways

Opportunity Detection is also real, but more derivative of existing options and conflict logic than the three above.

### 2. Which refinement is most tightly connected to how the trader actually makes or saves money?

Expression Quality is the most directly connected.

It governs:

- getting trapped in poor structures
- selecting clean vs tactical expressions
- preserving exit flexibility
- separating thesis validity from tradability quality

Exit Intelligence is second because it directly affects how losses get reduced and temporary spikes get monetized.

### 3. Is any refinement currently duplicated by an existing domain?

- Instrument Intelligence: partially overlaps with Options Behavior unless baseline instrument profile is separated from current-state options conditions
- Opportunity Detection: partially overlaps with Options Behavior and Conflict Rules unless permission vs opportunity is made explicit
- Expression Quality: small adjacency to Options Behavior, but not a duplicate if it focuses on expression cleanliness and chain-specific tradability
- Exit Intelligence: not duplicated today
- Trade State Awareness: not duplicated today
- Surface-Layer Visual Intelligence: not duplicated today

### 4. Which one deserves to become the next formal PRD?

Expression Quality

It is the most implementation-ready refinement that captures a genuine edge and cleanly extends the current architecture without forcing active position management into v1.

## 8. Recommended Scope Freeze

### Core v1

- existing domain agent contracts
- unified thesis engine
- conflict rules engine
- execution input contract
- audit and learning hooks

### Deferred

- Instrument Intelligence
- Opportunity Detection
- Expression Quality
- Exit Intelligence
- Trade State Awareness
- Surface-Layer Visual Intelligence

## 9. Decision Log

- [ ] Instrument Intelligence: Core v1 / Deferred / Rejected
- [ ] Opportunity Detection: Core v1 / Deferred / Rejected
- [ ] Expression Quality: Core v1 / Deferred / Rejected
- [ ] Exit Intelligence: Core v1 / Deferred / Rejected
- [ ] Trade State Awareness: Core v1 / Deferred / Rejected
- [ ] Surface-Layer Visual Intelligence: Core v1 / Deferred / Rejected

## 10. Suggested Next PRD

If one refinement is elevated next, it should be:

### Expression Quality

The next PRD should answer:

- What is the boundary between Options Behavior and Expression Quality?
- Is Expression Quality instrument-level, chain-level, or structure-level?
- Which outputs are advisory vs binding on Execution?
- How does the module express trap risk and exit flexibility without collapsing into a score soup?
