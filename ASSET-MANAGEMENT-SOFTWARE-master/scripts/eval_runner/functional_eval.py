#!/usr/bin/env python3
"""Functional eval runner — executes evals.json test cases via Claude API.

Loads a skill into the system prompt, sends test case inputs, and validates
assertions against the model response.

Usage:
    python -m scripts.eval_runner.functional_eval --skill assess-criticality
    python -m scripts.eval_runner.functional_eval --all --milestone 1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from scripts.eval_runner.models import (
    AssertionResult,
    EvalResult,
    EvalStatus,
    FunctionalEvalResult,
)

# ---------------------------------------------------------------------------
# Skill loading (reuses agent framework pattern)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _load_skill_body(skill_dir: Path) -> str:
    """Load the full CLAUDE.md content for a skill."""
    claude_md = skill_dir / "CLAUDE.md"
    if not claude_md.exists():
        return ""
    return claude_md.read_text(encoding="utf-8", errors="replace")


def _build_system_prompt(skill_body: str, include_skill: bool = True) -> str:
    """Build a system prompt with or without the skill loaded."""
    base = (
        "You are a maintenance engineering AI assistant. You help with asset "
        "management, reliability engineering, and maintenance strategy development "
        "for mining operations. Answer precisely using structured data when applicable. "
        "Always respond in the same language the user uses."
    )
    if include_skill and skill_body:
        return f"{base}\n\n# LOADED SKILL\n\n{skill_body}"
    return base


# ---------------------------------------------------------------------------
# Assertion checking
# ---------------------------------------------------------------------------

def _check_assertion(assertion_text: str, response_text: str, expected: dict) -> AssertionResult:
    """Check a single assertion against the response.

    Supports patterns:
      - "X equals Y" — exact match in response
      - "must report N ..." — count check
      - "must NOT ..." — absence check
      - "must request ..." — presence check
      - generic: check substring presence
    """
    lower_resp = response_text.lower()
    lower_assert = assertion_text.lower()

    # Pattern: "X equals Y"
    eq_match = re.match(r'(\w+)\s+equals?\s+(.+)', assertion_text, re.IGNORECASE)
    if eq_match:
        field = eq_match.group(1).strip()
        expected_val = eq_match.group(2).strip()
        # Check if the expected value appears in the response
        if expected_val.lower() in lower_resp:
            return AssertionResult(
                assertion=assertion_text,
                status=EvalStatus.PASS,
                expected_value=expected_val,
            )
        return AssertionResult(
            assertion=assertion_text,
            status=EvalStatus.FAIL,
            expected_value=expected_val,
            message=f"'{expected_val}' not found in response",
        )

    # Pattern: "must NOT ..."
    if "must not" in lower_assert or "should not" in lower_assert:
        # Extract what should be absent
        rest = re.sub(r'must\s+not\s+|should\s+not\s+', '', lower_assert).strip()
        keywords = [w for w in rest.split() if len(w) > 3]
        for kw in keywords:
            if kw in lower_resp:
                return AssertionResult(
                    assertion=assertion_text,
                    status=EvalStatus.FAIL,
                    message=f"Found '{kw}' in response (should be absent)",
                )
        return AssertionResult(assertion=assertion_text, status=EvalStatus.PASS)

    # Pattern: "must report N ..."
    count_match = re.match(r'must\s+report\s+(\d+)\s+', lower_assert)
    if count_match:
        expected_count = int(count_match.group(1))
        # Check if the number appears in response
        if str(expected_count) in response_text:
            return AssertionResult(
                assertion=assertion_text,
                status=EvalStatus.PASS,
                expected_value=expected_count,
            )
        return AssertionResult(
            assertion=assertion_text,
            status=EvalStatus.FAIL,
            expected_value=expected_count,
            message=f"Count {expected_count} not found in response",
        )

    # Pattern: "no ..." (absence)
    if lower_assert.startswith("no "):
        term = lower_assert[3:].strip()
        if term in lower_resp:
            return AssertionResult(
                assertion=assertion_text,
                status=EvalStatus.FAIL,
                message=f"Found '{term}' (expected absence)",
            )
        return AssertionResult(assertion=assertion_text, status=EvalStatus.PASS)

    # Generic: check if key assertion words appear in response
    keywords = [w for w in assertion_text.split() if len(w) > 3 and w.isalpha()]
    found = sum(1 for kw in keywords if kw.lower() in lower_resp)
    threshold = max(1, len(keywords) // 2)
    if found >= threshold:
        return AssertionResult(assertion=assertion_text, status=EvalStatus.PASS)
    return AssertionResult(
        assertion=assertion_text,
        status=EvalStatus.FAIL,
        message=f"Only {found}/{len(keywords)} key terms found in response",
    )


# ---------------------------------------------------------------------------
# Single eval execution
# ---------------------------------------------------------------------------

def run_single_eval(
    test_case: dict,
    skill_name: str,
    skill_body: str,
    include_skill: bool = True,
    model: str = "claude-sonnet-4-5-20250514",
) -> FunctionalEvalResult:
    """Execute one functional eval test case."""
    try:
        import anthropic
    except ImportError:
        return FunctionalEvalResult(
            eval_id=test_case.get("id", "unknown"),
            eval_name=test_case.get("name", "unknown"),
            skill_name=skill_name,
            status=EvalStatus.ERROR,
            error_message="anthropic package not installed",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return FunctionalEvalResult(
            eval_id=test_case.get("id", "unknown"),
            eval_name=test_case.get("name", "unknown"),
            skill_name=skill_name,
            status=EvalStatus.ERROR,
            error_message="ANTHROPIC_API_KEY not set",
        )

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _build_system_prompt(skill_body, include_skill)

    # Build user message from test case input
    input_data = test_case.get("input", {})
    user_msg = (
        f"Execute the following task for skill '{skill_name}'.\n\n"
        f"Input data:\n```json\n{json.dumps(input_data, indent=2)}\n```\n\n"
        f"Description: {test_case.get('description', '')}\n\n"
        f"Return structured results including all computed values."
    )

    start = time.monotonic()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        latency = (time.monotonic() - start) * 1000
        resp_text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
    except Exception as e:
        return FunctionalEvalResult(
            eval_id=test_case.get("id", "unknown"),
            eval_name=test_case.get("name", "unknown"),
            skill_name=skill_name,
            status=EvalStatus.ERROR,
            error_message=str(e),
        )

    # Check assertions
    expected = test_case.get("expected", {})
    assertion_results: list[AssertionResult] = []
    for assertion_text in test_case.get("assertions", []):
        assertion_results.append(_check_assertion(assertion_text, resp_text, expected))

    all_pass = all(a.status == EvalStatus.PASS for a in assertion_results)

    return FunctionalEvalResult(
        eval_id=test_case.get("id", "unknown"),
        eval_name=test_case.get("name", "unknown"),
        skill_name=skill_name,
        status=EvalStatus.PASS if all_pass else EvalStatus.FAIL,
        assertions=assertion_results,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency,
        raw_response=resp_text[:2000],
    )


# ---------------------------------------------------------------------------
# Batch execution
# ---------------------------------------------------------------------------

def run_functional_evals(
    skill_name: str,
    evals_path: Path,
    skill_dir: Path,
    include_skill: bool = True,
    model: str = "claude-sonnet-4-5-20250514",
) -> EvalResult:
    """Run all functional evals for one skill."""
    test_cases = json.loads(evals_path.read_text(encoding="utf-8"))
    skill_body = _load_skill_body(skill_dir) if include_skill else ""

    result = EvalResult(skill_name=skill_name, model=model)

    for tc in test_cases:
        eval_result = run_single_eval(tc, skill_name, skill_body, include_skill, model)
        result.results.append(eval_result)
        # Brief pause to avoid rate limits
        time.sleep(0.5)

    return result


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_functional_evals(project_root: Path) -> dict[str, tuple[Path, Path]]:
    """Find all evals.json files, keyed by skill name.

    Returns {skill_name: (evals_json_path, skill_dir)}.
    """
    skills_dir = project_root / "skills"
    result: dict[str, tuple[Path, Path]] = {}
    for f in skills_dir.rglob("evals.json"):
        if f.parent.name == "evals":
            skill_dir = f.parent.parent
            skill_name = skill_dir.name
            result[skill_name] = (f, skill_dir)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run functional evals")
    parser.add_argument("--skill", type=str, help="Specific skill to test")
    parser.add_argument("--all", action="store_true", help="Test all skills with evals")
    parser.add_argument("--no-skill", action="store_true", help="Run without skill (baseline)")
    parser.add_argument("--model", default="claude-sonnet-4-5-20250514")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    evals = find_functional_evals(args.project_root)

    if args.skill:
        skills_to_test = [args.skill]
    elif args.all:
        skills_to_test = sorted(evals.keys())
    else:
        print("Specify --skill NAME or --all", file=sys.stderr)
        sys.exit(1)

    all_results: list[EvalResult] = []
    for skill in skills_to_test:
        if skill not in evals:
            print(f"SKIP: {skill} — no evals.json", file=sys.stderr)
            continue

        evals_path, skill_dir = evals[skill]
        include_skill = not args.no_skill
        label = "with-skill" if include_skill else "without-skill"
        print(f"\nRunning {skill} ({label}, model={args.model})...", file=sys.stderr)

        result = run_functional_evals(skill, evals_path, skill_dir, include_skill, args.model)
        all_results.append(result)

        if args.format == "text":
            _print_result(result)

    if args.format == "json":
        import dataclasses
        print(json.dumps(
            [dataclasses.asdict(r) for r in all_results],
            indent=2, ensure_ascii=False, default=str,
        ))


def _print_result(result: EvalResult) -> None:
    print(f"\n{'=' * 60}")
    print(f"SKILL: {result.skill_name} | Model: {result.model}")
    print(f"Pass rate: {result.pass_rate:.1f}% | "
          f"Tokens: {result.total_tokens} | "
          f"Avg latency: {result.avg_latency_ms:.0f}ms")
    print(f"{'=' * 60}")
    for r in result.results:
        status = "PASS" if r.status == EvalStatus.PASS else "FAIL"
        print(f"  [{status}] {r.eval_name}")
        for a in r.assertions:
            a_status = "OK" if a.status == EvalStatus.PASS else "FAIL"
            msg = f" — {a.message}" if a.message else ""
            print(f"    [{a_status}] {a.assertion}{msg}")


if __name__ == "__main__":
    main()
