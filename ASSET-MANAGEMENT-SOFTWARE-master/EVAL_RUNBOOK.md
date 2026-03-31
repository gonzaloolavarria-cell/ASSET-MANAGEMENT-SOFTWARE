# Eval Runbook — AMS & OR SYSTEM

Step-by-step guide for executing the skill evaluation pipeline.

---

## Prerequisites

```bash
# Both systems
pip install -e ".[dev]"

# For functional evals / deep trigger mode
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Quick Reference

| Command | What it does | API key? | Time |
|---------|-------------|----------|------|
| `bash scripts/run_eval_suite.sh` | Full pipeline (trigger only) | No | ~30s |
| `bash scripts/run_eval_suite.sh --full` | Full pipeline + functional evals | Yes | ~10min |
| `bash scripts/run_eval_suite.sh --skill assess-criticality` | Single skill | No | ~2s |
| `bash scripts/run_eval_suite.sh --save-baseline` | Save baseline snapshot | No | ~30s |
| `bash scripts/run_eval_suite.sh --or-system` | Run on OR SYSTEM | No | ~2min |

---

## Step-by-Step Execution

### Step 1: Generate Evals for OR SYSTEM

OR SYSTEM starts with 0 evals. Generate them from CLAUDE.md files:

```bash
cd "g:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/OR SYSTEM"

# Dry run first to see what will be created
python scripts/generate_evals.py --project-root . --dry-run

# Generate for mandatory skills only (83 skills)
python scripts/generate_evals.py --project-root . --mandatory-only

# Generate for ALL skills (213 skills)
python scripts/generate_evals.py --project-root .

# Single skill
python scripts/generate_evals.py --project-root . --skill create-maintenance-strategy
```

**Output:** Creates `evals/trigger-eval.json` and `evals/evals.json` in each skill directory.

### Step 2: Run Trigger Optimization (Both Systems)

Optimize the `description` field in CLAUDE.md frontmatter for better trigger matching:

```bash
# --- AMS ---
cd "c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE"

# Preview changes (dry-run)
python scripts/optimize_triggers.py --project-root . --all

# Preview single skill
python scripts/optimize_triggers.py --project-root . --skill assess-criticality

# Apply changes
python scripts/optimize_triggers.py --project-root . --all --apply

# --- OR SYSTEM ---
cd "g:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/OR SYSTEM"

# Preview changes
python scripts/optimize_triggers.py --project-root . --all

# Apply changes
python scripts/optimize_triggers.py --project-root . --all --apply
```

**What it does:** Rewrites `description` to include "Use this skill when:" + "Do NOT use for:" patterns.

### Step 3: Create Initial Baselines

Run trigger evals and save results as the baseline for regression detection:

```bash
# --- AMS ---
cd "c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE"
python -m scripts.eval_runner.cli --project-root . snapshot --all --model claude-sonnet-4-5-20250514

# Verify
python -m scripts.eval_runner.cli --project-root . snapshot --list

# --- OR SYSTEM ---
cd "g:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/OR SYSTEM"
python -m scripts.eval_runner.cli --project-root . snapshot --all --model claude-sonnet-4-5-20250514
```

**Output:** JSON files in `evals/baselines/{model}/{skill}.json`.

### Step 4: Configure CI

Add `ANTHROPIC_API_KEY` as a repository secret in GitHub:

1. Go to **Settings > Secrets and variables > Actions**
2. Add `ANTHROPIC_API_KEY` with your API key
3. The workflow at `.github/workflows/skill-evals.yml` will run automatically on:
   - Push to master when skill files change
   - Weekly Sunday runs
   - Manual dispatch from Actions tab

---

## Individual Commands

### Audit

```bash
# Quality audit (score 0-100)
python scripts/audit_skills.py --project-root .

# Eval coverage audit (grade A-F)
python scripts/audit_eval_coverage.py --project-root .
```

### Trigger Evals

```bash
# Fast mode (TF-IDF, no API)
python -m scripts.eval_runner.cli --project-root . trigger --all --mode fast

# Deep mode (Claude-as-judge, needs API)
python -m scripts.eval_runner.cli --project-root . trigger --all --mode deep

# Single skill
python -m scripts.eval_runner.cli --project-root . trigger --skill assess-criticality --mode fast

# With report output
python -m scripts.eval_runner.cli --project-root . trigger --all --format markdown --output report.md
python -m scripts.eval_runner.cli --project-root . trigger --all --format json --output results.json
```

### Functional Evals

```bash
# Requires ANTHROPIC_API_KEY
python -m scripts.eval_runner.cli --project-root . functional --skill assess-criticality
python -m scripts.eval_runner.cli --project-root . functional --all --model claude-sonnet-4-5-20250514
```

### A/B Benchmark

```bash
# With-skill vs without-skill
python -m scripts.eval_runner.cli --project-root . benchmark --skill assess-criticality

# JSON output
python -m scripts.eval_runner.cli --project-root . benchmark --skill assess-criticality --format json
```

### Regression Detection

```bash
# Check against saved baselines
python -m scripts.eval_runner.cli --project-root . regression --all --output regression.md
python -m scripts.eval_runner.cli --project-root . regression --skill assess-criticality
```

---

## Execution Order for New Session

The recommended execution order when starting fresh:

```
1. OR: python scripts/generate_evals.py --project-root . [--mandatory-only]
2. AMS: python scripts/optimize_triggers.py --project-root . --all --apply
3. OR:  python scripts/optimize_triggers.py --project-root . --all --apply
4. AMS: python -m scripts.eval_runner.cli --project-root . trigger --all --mode fast
5. OR:  python -m scripts.eval_runner.cli --project-root . trigger --all --mode fast
6. AMS: python -m scripts.eval_runner.cli --project-root . snapshot --all
7. OR:  python -m scripts.eval_runner.cli --project-root . snapshot --all
```

Or use the all-in-one script:

```bash
# AMS
cd "c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE"
bash scripts/run_eval_suite.sh --save-baseline

# OR SYSTEM
cd "g:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/OR SYSTEM"
bash scripts/run_eval_suite.sh --generate --save-baseline
```

---

## Thresholds & Alerts

| Metric | Threshold | Action |
|--------|-----------|--------|
| Trigger accuracy | < 70% (AMS) / < 60% (OR) | Optimize description |
| Pass rate regression | > 10% drop | Investigate skill changes |
| Trigger regression | > 15% drop | Check if description was modified |
| Token increase | > 50% increase | Skill may confuse model |
| Skill quality score | < 50/100 | Add missing sections |
| Eval coverage | Grade F | Add trigger-eval.json + evals.json |

---

## File Reference

| File | System | Purpose |
|------|--------|---------|
| `scripts/eval_runner/cli.py` | Both | Unified CLI entry point |
| `scripts/eval_runner/trigger_eval.py` | Both | TF-IDF + Claude-as-judge trigger testing |
| `scripts/eval_runner/functional_eval.py` | Both | Functional eval execution via API |
| `scripts/eval_runner/benchmark.py` | Both | A/B testing engine |
| `scripts/eval_runner/snapshot.py` | Both | Baseline snapshot management |
| `scripts/eval_runner/regression.py` | Both | Regression detection |
| `scripts/eval_runner/reporter.py` | Both | Report generation (MD/JSON) |
| `scripts/eval_runner/models.py` | Both | Data models and enums |
| `scripts/audit_skills.py` | Both | Skill quality scoring |
| `scripts/audit_eval_coverage.py` | Both | Eval coverage grading |
| `scripts/optimize_triggers.py` | Both | Description optimizer |
| `scripts/generate_evals.py` | OR only | Auto-generate evals from CLAUDE.md |
| `scripts/run_eval_suite.sh` | Both | All-in-one runner script |
| `.github/workflows/skill-evals.yml` | Both | CI workflow |
| `SKILL_CLASSIFICATION.md` | `skills/` | Capability-uplift vs encoded-preference |
