# Client Culture Interview Guide v1.0 — Quick Reference

> **QUICK REFERENCE** — This is a condensed English summary for architecture reference.
> For the full canonical guide (Spanish, detailed), see `methodology/or-playbook/client-intent-interview-guide.md`.

**Component:** 2 of 7 (Wave 4 — Intent Engineering Layer)
**Purpose:** 3-layer interview to capture tacit knowledge, real values vs. declared values, and informal power dynamics.
**Reference:** `system-strategy-and-personalization/VSC_OR_Intent_Engineering_Strategy_v1.md`, Section 5.

---

## File Locations

| Artifact | Path |
|----------|------|
| This guide | `OR SYSTEM > methodology/or-playbook-and-procedures/client-intent-interview-guide.md` |
| Interview notes | `OR-SYSTEM-CLIENT > {project}/0-input/interview-notes/` |
| Output section | `intent-profile.yaml > full_context > organizational_reality_check` |

---

## 1. Purpose

The Excel questionnaire captures what the client **knows they know**. This interview captures what the client **doesn't know they know** — tacit knowledge, unwritten rules, real values (vs. declared), informal power dynamics.

> **Sequence:** The Web Intelligence Agent (Component 3) runs BEFORE this interview. Layer C uses the Web Agent's output for cross-validation questions.

---

## 2. Interview Structure: 3 Layers

### Layer A: Direct Questions (what the client knows they know)

**Duration:** 30-45 minutes.
**Interviewees:** Project Manager, Operations Manager, Plant Manager.

| ID | Question | What It Reveals |
|----|----------|----------------|
| A-01 | "What are the 3 KPIs that the general manager looks at first every Monday?" | Real business priority (not the declared one) |
| A-02 | "What happened the last time a project was delayed? How did the organization react?" | Schedule risk tolerance |
| A-03 | "If there's a conflict between meeting deadline and meeting safety standards, who decides and what do they decide?" | Real trade-off hierarchy |
| A-04 | "How long does it take to approve a USD 50K purchase order? And USD 500K?" | Decision speed and bureaucracy |
| A-05 | "Which area has the most decision-making power in this project?" | Power dynamics |
| A-06 | "Have you had a serious safety incident in the last 5 years? What changed afterwards?" | Real safety culture |
| A-07 | "Do you prefer we give you a best-practice solution or one adapted to your reality?" | Standard vs. custom preference |
| A-08 | "What is the most difficult decision you anticipate in this project?" | Anticipated tension points |
| A-09 | "What percentage of your current procedures are actually followed in the field?" | Gap between documentation and practice |
| A-10 | "If the OR project had to choose between delivering 10 perfect documents or 30 good ones, what do you prefer?" | Detail vs. speed |

### Layer B: Indirect Questions (what the client doesn't know they know)

**Duration:** 45-60 minutes.
**Interviewees:** Same as Layer A + first-line supervisors, senior operators.

| ID | Question | What It Reveals |
|----|----------|----------------|
| B-01 | "Tell me about a recent decision where you didn't follow the formal procedure. Why?" | Unwritten rules, pragmatism vs. compliance |
| B-02 | "If a new operator makes a mistake in the first month, what happens? And if they make it at 6 months?" | Learning culture vs. punishment |
| B-03 | "What kind of person does NOT survive in this organization?" | Implicit cultural values |
| B-04 | "Which area has the most staff turnover and why do you think that is?" | Hidden organizational problems |
| B-05 | "What happens when an area manager disagrees with a corporate decision?" | Autonomy vs. obedience |
| B-06 | "If tomorrow you had to cut 20% of this project's budget, what would you cut first? And what would you never cut?" | Real priorities under pressure |
| B-07 | "Is there something that 'everyone knows' but nobody says in formal meetings?" | Elephants in the room |
| B-08 | "How do you find out something is going wrong — through a report, a rumor, or a crisis?" | Real communication channels |
| B-09 | "How many meetings does a typical manager have per week? How many are useful?" | Organizational overhead |
| B-10 | "If you could change ONE thing about how this organization operates, what would it be?" | Main pain point |

### Layer C: Cross-Validation Questions (contrast statements with evidence)

**Duration:** 15-20 minutes (at end of interview).
**Requires:** Output from Web Intelligence Agent.

| ID | Question | Source of Contrast |
|----|----------|--------------------|
| C-01 | "Your website says you prioritize [value X]. How does that manifest in daily plant operations?" | Website vs. reality |
| C-02 | "In [news source] it was reported [incident/event]. How did that impact operations?" | News vs. internal perception |
| C-03 | "Your sustainability report mentions [ESG goal]. How close are you to meeting it?" | ESG report vs. reality |
| C-04 | "On employment platforms [employee feedback] appears. Does that reflect reality?" | Glassdoor/Indeed vs. internal culture |
| C-05 | "I noticed your competitor [name] did [action]. Does that create pressure in your organization?" | Competitive context |

---

## 3. Interview Protocol

| Aspect | Specification |
|--------|---------------|
| **Interviewer** | Senior VSC consultant (not the AI) |
| **Interviewees** | Minimum 3 levels: executive, middle manager, front line |
| **Total duration** | 2-3 hours distributed in 2-3 sessions |
| **Capture format** | Structured notes in `interview-notes/` (MD or DOCX) |
| **Confidentiality** | Layers B and C are confidential — not shared literally with the client |
| **Timing** | After Web Intelligence Agent, before completing the Excel (Sheets 2-3) |

### Time Allocation per Layer

| Layer | Questions | Time/Question | Total Layer Time | Interviewee Type |
|-------|-----------|--------------|-----------------|-----------------|
| A (Direct) | 10 | 3-4 min | 30-45 min | Executive, Manager |
| B (Indirect) | 10 | 4-6 min | 45-60 min | Manager, Supervisor, Operator |
| C (Cross-validation) | 5 | 3-4 min | 15-20 min | Same as A and B |
| **Total** | **25** | | **~90-125 min** | |

> **Note:** Not all questions are asked to every interviewee. The consultant selects the most relevant ones based on context. Layer B varies most in time — questions like B-07 ("something everyone knows but nobody says") can generate extensive responses.

---

## 4. Express Kit (Compressed Interview — 20 min)

When only 20-30 minutes are available instead of the full 90+ minutes:

| # | Question | Purpose |
|---|----------|---------|
| 1 | A-01: "What are the 3 KPIs the general manager looks at first?" | Real priorities |
| 2 | A-03: "If there's conflict between deadline and safety, who decides?" | Trade-off hierarchy |
| 3 | A-06: "Have you had a serious safety incident?" | Safety culture |
| 4 | B-06: "If you cut 20% of the budget, what goes first?" | Priorities under pressure |
| 5 | B-10: "If you could change ONE thing, what would it be?" | Main pain point |

---

## 5. Handling Difficult Situations

| Situation | Signals | Strategy |
|-----------|---------|----------|
| **Evasive executive** | Generic answers, avoids committing, uses "it depends" | Rephrase with concrete scenarios: "If tomorrow X happens, what would your organization do?" |
| **Over-positive respondent** | Everything is "excellent", denies problems | Use Layer B — indirect questions that reveal reality without confronting (B-01, B-06, B-07) |
| **Hostile/resistant stakeholder** | Perceives interview as threat, minimal answers | Empathize: "I understand these changes create concern. What we're looking for is..." + limit to 15 min |
| **No time (compressed interview)** | Only 20-30 min available | Use Express Kit above (5 essential questions) |

---

## 6. Output: Organizational Reality Check

Interview responses are synthesized into an Intent Profile section. **The AI generates the draft** from structured notes in `interview-notes/*.md`; **the consultant reviews, edits, and approves** the final content. The consultant has absolute editorial authority, especially over items marked as confidential (Layers B and C).

```yaml
organizational_reality_check:
  values_alignment:
    stated: [innovation, sustainability, people_first]
    observed: [cost_control, safety, loyalty]
    gap_signals:
      - "Declare innovation but R&D budget is 0.3% of revenue"
      - "Safety culture is strong post-incident of YYYY"
  decision_culture:
    formal: "Decentralized per org chart"
    actual: "Centralized — everything goes through VP Operations"
    bottleneck: "Purchase approvals >USD 50K take 3-4 weeks"
  unwritten_rules:
    - "Don't confront the VP in public meetings"
    - "Maintenance always loses budget to production"
    - "Field procedures are simplified in practice"
  risk_signals:
    - "High turnover in plant supervisors (burnout signal)"
    - "Gap between written SOPs and actual field practice ~30%"
  strengths:
    - "Very experienced maintenance team (avg 12 years)"
    - "Safety culture improved significantly post-YYYY"
```

This information is IP-L3 (loaded on demand only) but critically informs the decision zones and trade-offs encoded in IP-L1.

---

## 7. Mapping Questions to Intent Profile Fields

| Question ID | Maps to Intent Profile Field | Level |
|-------------|------------------------------|-------|
| A-01 | `intent_summary.primary_kpi` | IP-L1 |
| A-03 | `intent_summary.trade_off_priority` | IP-L1 |
| A-04 | `full_context.organizational_reality_check.decision_culture.bottleneck` | IP-L3 |
| A-06 | `domain_intent.hse.safety_culture_maturity` | IP-L2 |
| A-07 | Trade-off matrix TO-04 (standard vs custom) | IP-L1 |
| A-09 | `full_context.organizational_reality_check.risk_signals` | IP-L3 |
| B-01 | `full_context.organizational_reality_check.unwritten_rules` | IP-L3 |
| B-03 | `full_context.organizational_reality_check.values_alignment.observed` | IP-L3 |
| B-06 | `intent_summary.trade_off_priority` (validation) | IP-L1 |
| B-07 | `full_context.organizational_reality_check.risk_signals` | IP-L3 |
| C-01 to C-05 | `full_context.organizational_reality_check.values_alignment.gap_signals` | IP-L3 |
