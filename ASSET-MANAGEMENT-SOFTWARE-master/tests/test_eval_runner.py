"""Tests for the eval runner suite — audit, trigger eval, models, and reporter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scripts.eval_runner.models import (
    BenchmarkComparison,
    BenchmarkResult,
    EvalMode,
    EvalResult,
    EvalStatus,
    FunctionalEvalResult,
    SkillType,
    TriggerEvalResult,
    TriggerMatch,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_skill_dir(tmp_path: Path) -> Path:
    """Create a minimal skill directory for testing."""
    skill_dir = tmp_path / "skills" / "02-test" / "test-skill"
    skill_dir.mkdir(parents=True)

    claude_md = skill_dir / "CLAUDE.md"
    claude_md.write_text(
        '---\n'
        'name: test-skill\n'
        'description: >\n'
        '  Test skill for unit testing. Computes test metrics.\n'
        '  Triggers EN: test metric, compute test, run test analysis.\n'
        '  Triggers ES: metrica de prueba, calcular prueba, analisis de prueba.\n'
        '---\n'
        '# Test Skill\n'
        '## 1. Rol y Persona\n'
        'Test role.\n'
        '## 2. Intake - Informacion Requerida\n'
        '| Input | Type | Required | Description |\n'
        '|-------|------|----------|-------------|\n'
        '| equipment_id | string | Yes | Equipment ID |\n'
        '## 3. Flujo de Ejecucion\n'
        'Step 1. Do something.\n'
        '## 4. Logica de Decision\n'
        'Matrix here.\n'
        '## 5. Validacion\n'
        '1. Must validate all inputs.\n'
        '## 6. Recursos Vinculados\n'
        'None.\n'
        '## Common Pitfalls\n'
        '1. Do not skip validation.\n',
        encoding="utf-8",
    )

    # Create eval files
    evals_dir = skill_dir / "evals"
    evals_dir.mkdir()

    trigger_eval = {
        "skill": "test-skill",
        "should_trigger": [
            {"query": "Compute test metrics for equipment A", "reason": "Direct match"},
            {"query": "Run test analysis on pump P-101", "reason": "Keyword match"},
        ],
        "should_not_trigger": [
            {"query": "What is the weather today?", "reason": "Unrelated"},
            {"query": "Build equipment hierarchy", "reason": "Different skill"},
        ],
    }
    (evals_dir / "trigger-eval.json").write_text(json.dumps(trigger_eval), encoding="utf-8")

    functional_evals = [
        {
            "id": "test-001",
            "name": "Basic test",
            "description": "Test basic computation",
            "input": {"equipment_id": "EQ-001"},
            "expected": {"status": "success"},
            "assertions": ["status equals success"],
        },
    ]
    (evals_dir / "evals.json").write_text(json.dumps(functional_evals), encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestTriggerMatch:
    def test_pass_when_in_top_n(self):
        m = TriggerMatch(
            query="test", expected_skill="skill-a",
            matched_skills=["skill-a", "skill-b"],
            scores=[0.9, 0.5], in_top_n=True,
        )
        assert m.status == EvalStatus.PASS

    def test_fail_when_not_in_top_n(self):
        m = TriggerMatch(
            query="test", expected_skill="skill-a",
            matched_skills=["skill-b", "skill-c"],
            scores=[0.9, 0.5], in_top_n=False,
        )
        assert m.status == EvalStatus.FAIL


class TestTriggerEvalResult:
    def test_accuracy_calculation(self):
        r = TriggerEvalResult(skill_name="test", mode=EvalMode.FAST)
        r.should_trigger_results = [
            TriggerMatch("q1", "test", ["test"], [1.0], in_top_n=True),
            TriggerMatch("q2", "test", ["other"], [1.0], in_top_n=False),
        ]
        assert r.trigger_accuracy == 50.0

    def test_empty_results(self):
        r = TriggerEvalResult(skill_name="test", mode=EvalMode.FAST)
        assert r.trigger_accuracy == 0.0
        assert r.overall_accuracy == 0.0


class TestEvalResult:
    def test_pass_rate(self):
        r = EvalResult(skill_name="test", model="test-model")
        r.results = [
            FunctionalEvalResult("e1", "t1", "test", EvalStatus.PASS),
            FunctionalEvalResult("e2", "t2", "test", EvalStatus.FAIL),
            FunctionalEvalResult("e3", "t3", "test", EvalStatus.PASS),
        ]
        assert abs(r.pass_rate - 66.7) < 0.1

    def test_empty_pass_rate(self):
        r = EvalResult(skill_name="test")
        assert r.pass_rate == 0.0


class TestBenchmarkComparison:
    def test_recommendation_a_better(self):
        eval_a = EvalResult(skill_name="test")
        eval_a.results = [FunctionalEvalResult("e1", "t1", "test", EvalStatus.PASS)] * 10
        eval_b = EvalResult(skill_name="test")
        eval_b.results = [FunctionalEvalResult("e1", "t1", "test", EvalStatus.FAIL)] * 10

        comp = BenchmarkComparison(
            skill_name="test",
            skill_type=SkillType.CAPABILITY_UPLIFT,
            condition_a=BenchmarkResult("with-skill", "test", "model", eval_a),
            condition_b=BenchmarkResult("without-skill", "test", "model", eval_b),
        )
        assert "with-skill" in comp.recommendation
        assert comp.pass_rate_delta == 100.0


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------

class TestAuditSkills:
    def test_discover_skills(self, sample_skill_dir: Path):
        from scripts.audit_skills import discover_skills
        skills = discover_skills(sample_skill_dir)
        assert len(skills) == 1
        assert skills[0].name == "test-skill"

    def test_audit_skill_quality(self, sample_skill_dir: Path):
        from scripts.audit_skills import audit_skill, discover_skills
        skills = discover_skills(sample_skill_dir)
        result = audit_skill(skills[0])
        assert result.name == "test-skill"
        assert result.has_evals_json is True
        assert result.has_trigger_eval_json is True
        assert result.triggers_en_count >= 3
        assert result.description_under_1024 is True
        assert result.score > 0

    def test_detect_missing_evals(self, tmp_path: Path):
        from scripts.audit_skills import audit_skill
        skill_dir = tmp_path / "skills" / "02-test" / "no-eval-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "CLAUDE.md").write_text(
            "---\nname: no-eval\ndescription: test\n---\n# No Eval\n",
            encoding="utf-8",
        )
        result = audit_skill(skill_dir)
        assert result.has_evals_json is False
        assert result.has_trigger_eval_json is False
        assert "Missing evals/evals.json" in result.issues


class TestAuditEvalCoverage:
    def test_grade_a_skill(self, sample_skill_dir: Path):
        from scripts.audit_eval_coverage import audit_eval_coverage, discover_skills
        skills = discover_skills(sample_skill_dir)
        result = audit_eval_coverage(skills[0])
        assert result.has_evals_json is True
        assert result.has_trigger_eval_json is True

    def test_grade_f_skill(self, tmp_path: Path):
        from scripts.audit_eval_coverage import audit_eval_coverage
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir(parents=True)
        result = audit_eval_coverage(skill_dir)
        assert result.coverage_grade == "F"


# ---------------------------------------------------------------------------
# Trigger eval tests
# ---------------------------------------------------------------------------

class TestTriggerEval:
    def test_tfidf_matcher(self):
        from scripts.eval_runner.trigger_eval import TfIdfMatcher
        catalog = {
            "assess-criticality": "Assess equipment criticality using risk matrix R8 method",
            "perform-fmeca": "Perform failure mode effects and criticality analysis FMECA",
            "build-hierarchy": "Build equipment hierarchy using ISO 14224 taxonomy",
        }
        matcher = TfIdfMatcher(catalog)
        matches = matcher.match("What is the criticality of our pump?", top_n=3)
        assert matches[0][0] == "assess-criticality"

    def test_tfidf_matcher_no_crash_empty(self):
        from scripts.eval_runner.trigger_eval import TfIdfMatcher
        matcher = TfIdfMatcher({"a": "test"})
        matches = matcher.match("", top_n=3)
        assert len(matches) >= 1

    def test_build_catalog(self, sample_skill_dir: Path):
        from scripts.eval_runner.trigger_eval import build_skill_catalog
        catalog = build_skill_catalog(sample_skill_dir)
        assert "test-skill" in catalog

    def test_run_trigger_eval_fast(self, sample_skill_dir: Path):
        from scripts.eval_runner.trigger_eval import (
            build_skill_catalog,
            find_trigger_evals,
            run_trigger_eval_fast,
        )
        catalog = build_skill_catalog(sample_skill_dir)
        trigger_evals = find_trigger_evals(sample_skill_dir)
        assert "test-skill" in trigger_evals

        result = run_trigger_eval_fast("test-skill", trigger_evals["test-skill"], catalog)
        assert isinstance(result, TriggerEvalResult)
        assert result.skill_name == "test-skill"
        assert len(result.should_trigger_results) == 2
        assert len(result.should_not_trigger_results) == 2


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_save_and_load(self, tmp_path: Path):
        from scripts.eval_runner.snapshot import save_snapshot, load_snapshot
        metrics = {"pass_rate": 95.0, "trigger_accuracy": 90.0}
        save_snapshot("test-skill", "test-model", metrics, tmp_path)

        loaded = load_snapshot("test-skill", "test-model", tmp_path)
        assert loaded is not None
        assert loaded["metrics"]["pass_rate"] == 95.0

    def test_load_nonexistent(self, tmp_path: Path):
        from scripts.eval_runner.snapshot import load_snapshot
        result = load_snapshot("nonexistent", "model", tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

class TestRegression:
    def test_no_regression_when_stable(self, tmp_path: Path):
        from scripts.eval_runner.snapshot import save_snapshot
        from scripts.eval_runner.regression import check_regression

        save_snapshot("test-skill", "model", {"pass_rate": 90.0}, tmp_path)
        report = check_regression("test-skill", "model", {"pass_rate": 89.0}, tmp_path)
        assert report.is_clean  # 1% drop is within threshold

    def test_regression_detected(self, tmp_path: Path):
        from scripts.eval_runner.snapshot import save_snapshot
        from scripts.eval_runner.regression import check_regression

        save_snapshot("test-skill", "model", {"pass_rate": 90.0}, tmp_path)
        report = check_regression("test-skill", "model", {"pass_rate": 70.0}, tmp_path)
        assert not report.is_clean
        assert len(report.alerts) == 1
        assert report.alerts[0].metric == "pass_rate"

    def test_obsolescence_detection(self):
        from scripts.eval_runner.regression import check_obsolescence
        assert check_obsolescence("skill", 80.0, 85.0) is True  # Without > With
        assert check_obsolescence("skill", 90.0, 70.0) is False  # With >> Without


# ---------------------------------------------------------------------------
# Reporter tests
# ---------------------------------------------------------------------------

class TestReporter:
    def test_trigger_report_markdown(self):
        from scripts.eval_runner.reporter import trigger_report_markdown
        r = TriggerEvalResult(skill_name="test", mode=EvalMode.FAST)
        r.should_trigger_results = [
            TriggerMatch("q1", "test", ["test"], [1.0], in_top_n=True),
        ]
        report = trigger_report_markdown([r])
        assert "# Trigger Eval Report" in report
        assert "test" in report

    def test_save_report(self, tmp_path: Path):
        from scripts.eval_runner.reporter import save_report
        save_report("test content", tmp_path / "report.md")
        assert (tmp_path / "report.md").read_text() == "test content"
