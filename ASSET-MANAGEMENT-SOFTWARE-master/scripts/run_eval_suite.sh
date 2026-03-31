#!/usr/bin/env bash
# =============================================================================
# Skill Eval Suite — AMS
#
# Runs the complete evaluation pipeline in order:
#   1. Audit skills quality
#   2. Audit eval coverage
#   3. Run trigger evals (fast TF-IDF, no API key needed)
#   4. Optimize trigger descriptions (dry-run by default)
#   5. Run functional evals (requires ANTHROPIC_API_KEY)
#   6. Save baseline snapshots
#   7. Run regression check against baselines
#
# Usage:
#   bash scripts/run_eval_suite.sh                    # All steps (trigger only)
#   bash scripts/run_eval_suite.sh --full             # Include functional evals
#   bash scripts/run_eval_suite.sh --skill NAME       # Single skill
#   bash scripts/run_eval_suite.sh --save-baseline    # Save results as baseline
#   bash scripts/run_eval_suite.sh --apply-triggers   # Apply trigger optimizations
#   bash scripts/run_eval_suite.sh --or-system        # Run on OR SYSTEM instead
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
OR_SYSTEM_ROOT="g:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/OR SYSTEM"

SKILL_FLAG="--all"
MODE="fast"
RUN_FUNCTIONAL=false
SAVE_BASELINE=false
APPLY_TRIGGERS=false
USE_OR_SYSTEM=false
OUTPUT_DIR="${PROJECT_ROOT}/output/eval-reports"
MODEL="claude-sonnet-4-5-20250514"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skill)
            SKILL_FLAG="--skill $2"
            shift 2
            ;;
        --full)
            RUN_FUNCTIONAL=true
            shift
            ;;
        --save-baseline)
            SAVE_BASELINE=true
            shift
            ;;
        --apply-triggers)
            APPLY_TRIGGERS=true
            shift
            ;;
        --or-system)
            USE_OR_SYSTEM=true
            PROJECT_ROOT="${OR_SYSTEM_ROOT}"
            shift
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --help|-h)
            head -20 "$0" | grep '^#' | sed 's/^# *//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mkdir -p "${OUTPUT_DIR}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "============================================================"
echo " Skill Eval Suite — $(basename "${PROJECT_ROOT}")"
echo " Started: $(date)"
echo " Project: ${PROJECT_ROOT}"
echo " Skill:   ${SKILL_FLAG}"
echo " Mode:    ${MODE}"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Audit skills quality
# ---------------------------------------------------------------------------
echo ">>> Step 1/7: Skill Quality Audit"
python "${SCRIPT_DIR}/audit_skills.py" \
    --project-root "${PROJECT_ROOT}" \
    2>&1 | tee "${OUTPUT_DIR}/audit_${TIMESTAMP}.txt"
echo ""

# ---------------------------------------------------------------------------
# Step 2: Audit eval coverage
# ---------------------------------------------------------------------------
echo ">>> Step 2/7: Eval Coverage Audit"
python "${SCRIPT_DIR}/audit_eval_coverage.py" \
    --project-root "${PROJECT_ROOT}" \
    2>&1 | tee "${OUTPUT_DIR}/coverage_${TIMESTAMP}.txt"
echo ""

# ---------------------------------------------------------------------------
# Step 3: Generate evals for OR SYSTEM (if applicable)
# ---------------------------------------------------------------------------
if [ "${USE_OR_SYSTEM}" = true ]; then
    echo ">>> Step 3 (OR only): Generate Evals"
    python "${SCRIPT_DIR}/generate_evals.py" \
        --project-root "${PROJECT_ROOT}" \
        2>&1 | tee "${OUTPUT_DIR}/generate_evals_${TIMESTAMP}.txt"
    echo ""
fi

# ---------------------------------------------------------------------------
# Step 4: Trigger Evals
# ---------------------------------------------------------------------------
echo ">>> Step 4/7: Trigger Evals (${MODE} mode)"
python -m scripts.eval_runner.cli --project-root "${PROJECT_ROOT}" \
    trigger ${SKILL_FLAG} \
    --mode "${MODE}" \
    --format markdown \
    --output "${OUTPUT_DIR}/trigger_report_${TIMESTAMP}.md"

python -m scripts.eval_runner.cli --project-root "${PROJECT_ROOT}" \
    trigger ${SKILL_FLAG} \
    --mode "${MODE}" \
    --format json \
    --output "${OUTPUT_DIR}/trigger_results_${TIMESTAMP}.json"

echo "  Report: ${OUTPUT_DIR}/trigger_report_${TIMESTAMP}.md"
echo ""

# ---------------------------------------------------------------------------
# Step 5: Optimize Triggers (dry-run unless --apply-triggers)
# ---------------------------------------------------------------------------
echo ">>> Step 5/7: Trigger Description Optimization"
if [ "${APPLY_TRIGGERS}" = true ]; then
    echo "  Mode: APPLY (writing changes to CLAUDE.md files)"
    python "${SCRIPT_DIR}/optimize_triggers.py" \
        --project-root "${PROJECT_ROOT}" \
        --all --apply \
        2>&1 | tee "${OUTPUT_DIR}/optimize_triggers_${TIMESTAMP}.txt"
else
    echo "  Mode: DRY-RUN (use --apply-triggers to write changes)"
    python "${SCRIPT_DIR}/optimize_triggers.py" \
        --project-root "${PROJECT_ROOT}" \
        --all \
        2>&1 | tee "${OUTPUT_DIR}/optimize_triggers_${TIMESTAMP}.txt"
fi
echo ""

# ---------------------------------------------------------------------------
# Step 6: Functional Evals (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------
if [ "${RUN_FUNCTIONAL}" = true ]; then
    echo ">>> Step 6/7: Functional Evals"
    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo "  SKIP: ANTHROPIC_API_KEY not set"
        echo "  Set it with: export ANTHROPIC_API_KEY=sk-ant-..."
    else
        python -m scripts.eval_runner.cli --project-root "${PROJECT_ROOT}" \
            functional ${SKILL_FLAG} \
            --model "${MODEL}" \
            2>&1 | tee "${OUTPUT_DIR}/functional_${TIMESTAMP}.txt"
    fi
else
    echo ">>> Step 6/7: Functional Evals — SKIPPED (use --full to enable)"
fi
echo ""

# ---------------------------------------------------------------------------
# Step 7: Baseline & Regression
# ---------------------------------------------------------------------------
if [ "${SAVE_BASELINE}" = true ]; then
    echo ">>> Step 7/7: Saving Baseline Snapshots"
    python -m scripts.eval_runner.cli --project-root "${PROJECT_ROOT}" \
        snapshot ${SKILL_FLAG} \
        --model "${MODEL}"
    echo "  Baselines saved."
else
    echo ">>> Step 7/7: Regression Check"
    python -m scripts.eval_runner.cli --project-root "${PROJECT_ROOT}" \
        regression ${SKILL_FLAG} \
        --model "${MODEL}" \
        --output "${OUTPUT_DIR}/regression_${TIMESTAMP}.md" \
        2>&1 || echo "  No baselines found — run with --save-baseline first"
fi
echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "============================================================"
echo " Eval Suite Complete"
echo " Finished: $(date)"
echo " Reports:  ${OUTPUT_DIR}/"
echo "============================================================"
echo ""
echo "Files generated:"
ls -la "${OUTPUT_DIR}/"*"${TIMESTAMP}"* 2>/dev/null || echo "  (none)"
