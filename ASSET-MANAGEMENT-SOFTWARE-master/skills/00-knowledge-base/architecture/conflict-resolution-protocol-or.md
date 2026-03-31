# Conflict Resolution Protocol — VSC OR Multi-Agent System

**Version:** 1.0.0
**Effective:** Wave 4 — Intent Engineering Layer

## Purpose

When two or more agents produce contradictory recommendations for the same asset, system, or decision, the Orchestrator invokes this protocol to resolve the conflict transparently and traceably.

Without this protocol, conflicts are resolved implicitly by processing order — which is opaque, inconsistent, and not auditable.

## Conflict Types

| Type | Example | Frequency |
|------|---------|-----------|
| **Priority** | HSE says "stop the activity" vs. Execution says "the schedule is at risk" | High |
| **Resource** | Operations wants 200 operators vs. Finance says budget covers only 150 | Medium |
| **Scope** | Asset Mgmt recommends predictive PM vs. C&C says no qualified vendor | Medium |
| **Timing** | Engineering says "design incomplete" vs. Construction says "already started" | High |
| **Methodology** | Asset Mgmt uses RCM for all equipment vs. Ops says "run-to-failure is sufficient for class C" | Low |

## 5-Step Resolution Protocol

### Step 1: Detection (Automatic, Immediate)

The Orchestrator detects a conflict when:
- Two agents generate contradictory recommendations for the same asset/system.
- An agent objects to another agent's output during peer review.
- Cross-deliverable consistency check fails (QA Layer 3).

### Step 2: Classification (<5 minutes, Automatic)

Does the conflict involve a veto rule?
- **YES** → Apply veto immediately (skip to Step 5).
- **NO** → Continue to Step 3.

### Step 3: Trade-Off Hierarchy Lookup (<10 minutes, Automatic)

Read `trade_off_matrix` from the project's `intent-profile.yaml`:
1. Identify the conflict type (e.g., `cost_vs_availability`, `speed_vs_safety`).
2. Compare weights: if `weight_a > weight_b + 2` → resolve in favor of A.
3. If difference <= 2 → conflict is ambiguous, proceed to Step 4.

### Step 4: Escalation with Recommendation

The Orchestrator generates a **Conflict Resolution Brief (CRB)** containing:
- Description of the conflict
- Position of each agent (with technical justification)
- Trade-off analysis (weights from Intent Profile)
- Orchestrator's recommendation
- Impact comparison for each option (cost, schedule, risk, quality)

Send to consultant for decision. If the decision affects budget envelope or client commitments, escalate to client.

**SLA:** Consultant response <2 hours. Client response <24 hours.

### Step 5: Record and Learn (<5 minutes, Automatic)

1. Record the decision in `state/intent-conflict-log.md`.
2. If the decision contradicts the trade-off hierarchy → flag for Intent Profile update.
3. If the same conflict type repeats >3 times:
   a. If all N resolutions were consistent (same direction) → propose new veto rule.
   b. If resolutions were mixed → propose weight adjustment in trade-off matrix.
   c. Consultant approves/rejects the proposal. If approved → update `intent-profile.yaml` automatically.

## No-Response Protocol

If the consultant does not respond to an escalation (Step 4) within the SLA:

| Time | Action |
|------|--------|
| +2 hours | Orchestrator sends reminder with elevated urgency |
| +4 hours | Escalation marked as "PENDING — AWAITING RESPONSE" |
| +8 hours | Task marked as "BLOCKED", downstream dependencies notified |
| +24 hours | Task paused, all dependent tasks suspended, alert sent to project sponsor |

**Temporary Resolution:** If the decision is urgent (blocks critical path) and the consultant does not respond within 4 hours, the Orchestrator may apply the default resolution from the trade-off hierarchy with flag "AUTO-RESOLVED — PENDING CONFIRMATION". The consultant must confirm or revert upon reconnection.

## Veto System

Certain domains have absolute veto in specific situations:

| Domain | Veto Condition | Override Possible |
|--------|---------------|-------------------|
| HSE | Fatality risk or serious harm to persons | No — never |
| HSE | Confirmed regulatory non-compliance | No — never |
| HSE | High-category environmental risk | Yes — with VP approval + mitigation plan |
| Finance | Exceeds approved budget envelope | Yes — with formal re-forecast approved by sponsor |
| Execution | Impacts first production date (if marked as immovable) | No — requires board-level escalation |
| C&C | Violation of signed contractual clause | Yes — with formal change order |

## Conflict Resolution Brief Template

```markdown
# Conflict Resolution Brief — CRB-{NNN}

**Date:** YYYY-MM-DD
**Conflict between:** [Agent A] vs. [Agent B]
**Affected system/asset:** [identifier]
**Conflict type:** [priority | resource | scope | timing | methodology]

## Positions

### [Agent A] recommends:
[Description + technical justification]

### [Agent B] recommends:
[Description + technical justification]

## Trade-Off Analysis
- Conflict maps to: [type from trade_off_matrix]
- Weight Option A: [N]/10
- Weight Option B: [N]/10
- Difference: [N] (>2 = clear resolution, <=2 = ambiguous)

## Impact Comparison

| Dimension | If A accepted | If B accepted |
|-----------|--------------|--------------|
| Cost | +/- USD X | +/- USD Y |
| Schedule | +/- N days | +/- N days |
| Risk | Level X | Level Y |
| Quality | Impact X | Impact Y |

## Orchestrator Recommendation
[Reasoned recommendation]

## Decision
**Decided by:** [consultant | client | automatic veto]
**Decision:** [A | B | alternative C]
**Reason:** [free text]
```

## Conflict Tracking Log

All conflicts and their resolutions are recorded in `{project}/state/intent-conflict-log.md`:

```markdown
# Intent Conflict Log — {Project}

| # | Date | Agents | Type | Trade-off | Resolution | Decided by | Time |
|---|------|--------|------|-----------|------------|------------|------|
| 1 | 2026-03-15 | HSE vs Exec | Priority | speed_vs_safety | Safety first — ramp-up extended 2 weeks | Auto veto | <5 min |
| 2 | 2026-03-22 | AM vs Finance | Resource | cost_vs_availability | Spare parts reduced 15% keeping critical items | Consultant | 1.5h |
| 3 | 2026-04-01 | Ops vs HR | Resource | staffing budget | Headcount reduced with planned overtime | Client | 18h |
```

**Log usage:**
- The Orchestrator consults the log to detect patterns (>3 repetitions of the same type → trigger learning in Step 5).
- The consultant uses it in gate reviews to report resolved and pending conflicts.
- Derived metrics: average resolution time, % auto-resolved vs. escalated, agents most frequently in conflict.

## Integration with Intent Profile

This protocol depends on two sections of `intent-profile.yaml`:

1. **`trade_off_matrix`** — Provides weights for automatic resolution (Step 3).
2. **`veto_rules`** — Defines unconditional overrides (Step 2).

If no `intent-profile.yaml` exists (v3.1 mode), all conflicts escalate directly to Step 4 (consultant decision) since there is no trade-off hierarchy to consult.
