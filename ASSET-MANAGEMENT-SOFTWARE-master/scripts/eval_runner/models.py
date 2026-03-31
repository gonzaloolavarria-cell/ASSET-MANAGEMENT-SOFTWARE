"""Data models for eval runner results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SkillType(str, Enum):
    CAPABILITY_UPLIFT = "capability-uplift"
    ENCODED_PREFERENCE = "encoded-preference"


class EvalMode(str, Enum):
    FAST = "fast"       # TF-IDF / keyword matching (no API calls)
    DEEP = "deep"       # Claude-as-judge (requires API)


class EvalStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


# ---------------------------------------------------------------------------
# Trigger Eval
# ---------------------------------------------------------------------------

@dataclass
class TriggerMatch:
    """Result of matching a query against skill descriptions."""
    query: str
    expected_skill: str
    matched_skills: list[str]       # top-N matched skills
    scores: list[float]             # similarity scores for each match
    in_top_n: bool = False          # expected_skill in top-N
    mode: EvalMode = EvalMode.FAST

    @property
    def status(self) -> EvalStatus:
        return EvalStatus.PASS if self.in_top_n else EvalStatus.FAIL


@dataclass
class TriggerEvalResult:
    """Results of running trigger evals for one skill."""
    skill_name: str
    mode: EvalMode
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # should_trigger results
    should_trigger_results: list[TriggerMatch] = field(default_factory=list)
    # should_not_trigger results
    should_not_trigger_results: list[TriggerMatch] = field(default_factory=list)

    @property
    def trigger_accuracy(self) -> float:
        """Percentage of should_trigger queries correctly matched."""
        if not self.should_trigger_results:
            return 0.0
        passed = sum(1 for r in self.should_trigger_results if r.status == EvalStatus.PASS)
        return passed / len(self.should_trigger_results) * 100

    @property
    def anti_trigger_accuracy(self) -> float:
        """Percentage of should_not_trigger queries correctly rejected."""
        if not self.should_not_trigger_results:
            return 0.0
        # For should_not_trigger, PASS means the skill was NOT in top-N
        passed = sum(1 for r in self.should_not_trigger_results if r.status == EvalStatus.FAIL)
        return passed / len(self.should_not_trigger_results) * 100

    @property
    def overall_accuracy(self) -> float:
        total = len(self.should_trigger_results) + len(self.should_not_trigger_results)
        if total == 0:
            return 0.0
        correct = (
            sum(1 for r in self.should_trigger_results if r.status == EvalStatus.PASS)
            + sum(1 for r in self.should_not_trigger_results if r.status == EvalStatus.FAIL)
        )
        return correct / total * 100


# ---------------------------------------------------------------------------
# Functional Eval
# ---------------------------------------------------------------------------

@dataclass
class AssertionResult:
    """Result of a single assertion check."""
    assertion: str
    status: EvalStatus
    actual_value: Any = None
    expected_value: Any = None
    message: str = ""


@dataclass
class FunctionalEvalResult:
    """Result of running one functional eval test case."""
    eval_id: str
    eval_name: str
    skill_name: str
    status: EvalStatus
    assertions: list[AssertionResult] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    raw_response: str = ""
    error_message: str = ""


@dataclass
class EvalResult:
    """Aggregated results of all functional evals for one skill."""
    skill_name: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model: str = ""
    results: list[FunctionalEvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        passed = sum(1 for r in self.results if r.status == EvalStatus.PASS)
        return passed / len(self.results) * 100

    @property
    def total_tokens(self) -> int:
        return sum(r.input_tokens + r.output_tokens for r in self.results)

    @property
    def avg_latency_ms(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.latency_ms for r in self.results) / len(self.results)


# ---------------------------------------------------------------------------
# Benchmark (A/B Testing)
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """Results of a benchmark run (one condition: with-skill or without-skill)."""
    condition: str          # "with-skill", "without-skill", "v1", "v2"
    skill_name: str
    model: str
    eval_result: EvalResult
    trigger_result: TriggerEvalResult | None = None

    @property
    def pass_rate(self) -> float:
        return self.eval_result.pass_rate

    @property
    def total_tokens(self) -> int:
        return self.eval_result.total_tokens

    @property
    def avg_latency_ms(self) -> float:
        return self.eval_result.avg_latency_ms

    @property
    def trigger_accuracy(self) -> float:
        return self.trigger_result.overall_accuracy if self.trigger_result else 0.0


@dataclass
class BenchmarkComparison:
    """Comparison between two benchmark conditions (A/B test)."""
    skill_name: str
    skill_type: SkillType
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    condition_a: BenchmarkResult | None = None
    condition_b: BenchmarkResult | None = None

    @property
    def pass_rate_delta(self) -> float:
        """Positive = A is better."""
        if not self.condition_a or not self.condition_b:
            return 0.0
        return self.condition_a.pass_rate - self.condition_b.pass_rate

    @property
    def token_delta(self) -> int:
        """Positive = A uses more tokens."""
        if not self.condition_a or not self.condition_b:
            return 0
        return self.condition_a.total_tokens - self.condition_b.total_tokens

    @property
    def latency_delta_ms(self) -> float:
        """Positive = A is slower."""
        if not self.condition_a or not self.condition_b:
            return 0.0
        return self.condition_a.avg_latency_ms - self.condition_b.avg_latency_ms

    @property
    def recommendation(self) -> str:
        """Simple recommendation based on deltas."""
        if not self.condition_a or not self.condition_b:
            return "Insufficient data"
        a_label = self.condition_a.condition
        b_label = self.condition_b.condition

        if self.pass_rate_delta > 5:
            return f"{a_label} is significantly better (+{self.pass_rate_delta:.1f}% pass rate)"
        if self.pass_rate_delta < -5:
            return f"{b_label} is significantly better (+{abs(self.pass_rate_delta):.1f}% pass rate)"
        if abs(self.token_delta) > 1000:
            cheaper = a_label if self.token_delta < 0 else b_label
            return f"Similar quality — {cheaper} uses fewer tokens"
        return "No significant difference"
