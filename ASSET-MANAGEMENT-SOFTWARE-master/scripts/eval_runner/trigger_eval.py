#!/usr/bin/env python3
"""Trigger eval runner — Dual-mode skill trigger testing.

Fast mode:  TF-IDF keyword matching against skill descriptions (no API).
Deep mode:  Claude-as-judge selects which skill to use (requires API key).

Usage:
    python -m scripts.eval_runner.trigger_eval --skill assess-criticality --mode fast
    python -m scripts.eval_runner.trigger_eval --all --mode fast
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

from scripts.eval_runner.models import (
    EvalMode,
    TriggerEvalResult,
    TriggerMatch,
)

# ---------------------------------------------------------------------------
# Frontmatter extraction (shared with audit_skills)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _extract_description(claude_md_path: Path) -> str:
    """Extract the description field from a CLAUDE.md frontmatter."""
    text = claude_md_path.read_text(encoding="utf-8", errors="replace")
    m = _FM_RE.match(text)
    if not m:
        return ""
    raw = m.group(1)
    # Simple YAML extraction for description
    lines = raw.split("\n")
    in_desc = False
    desc_lines: list[str] = []
    for line in lines:
        if re.match(r'^description\s*:', line):
            in_desc = True
            val = re.sub(r'^description\s*:\s*', '', line).strip().strip('"').strip("'")
            if val and val not in (">", "|"):
                desc_lines.append(val)
            continue
        if in_desc:
            if re.match(r'^\w[\w-]*\s*:', line) and not line.startswith(" "):
                break
            desc_lines.append(line.strip())
    return " ".join(desc_lines).strip()


# ---------------------------------------------------------------------------
# Skill catalog builder
# ---------------------------------------------------------------------------

def build_skill_catalog(project_root: Path) -> dict[str, str]:
    """Build {skill_name: description} mapping from all skills."""
    skills_dir = project_root / "skills"
    catalog: dict[str, str] = {}
    for claude_md in skills_dir.rglob("CLAUDE.md"):
        rel = claude_md.relative_to(skills_dir)
        if str(rel).startswith("00-knowledge-base"):
            continue
        skill_name = claude_md.parent.name
        desc = _extract_description(claude_md)
        if desc:
            catalog[skill_name] = desc
    return catalog


# ---------------------------------------------------------------------------
# Fast mode: TF-IDF matching
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    return re.findall(r'[a-záéíóúñü]+', text.lower())


class TfIdfMatcher:
    """Lightweight TF-IDF matcher — no external dependencies."""

    def __init__(self, catalog: dict[str, str]) -> None:
        self.skill_names = list(catalog.keys())
        self.descriptions = [catalog[n] for n in self.skill_names]
        self._build_index()

    def _build_index(self) -> None:
        """Build inverted index and IDF values."""
        self.doc_tokens: list[list[str]] = []
        self.doc_tf: list[dict[str, float]] = []
        df: Counter[str] = Counter()

        for desc in self.descriptions:
            tokens = _tokenize(desc)
            self.doc_tokens.append(tokens)
            tf = Counter(tokens)
            total = len(tokens) or 1
            self.doc_tf.append({t: c / total for t, c in tf.items()})
            for t in set(tokens):
                df[t] += 1

        n = len(self.descriptions) or 1
        self.idf: dict[str, float] = {
            t: math.log((n + 1) / (count + 1)) + 1
            for t, count in df.items()
        }

    def match(self, query: str, top_n: int = 3) -> list[tuple[str, float]]:
        """Return top-N (skill_name, score) matches for a query."""
        q_tokens = _tokenize(query)
        q_tf = Counter(q_tokens)
        q_total = len(q_tokens) or 1

        scores: list[tuple[str, float]] = []
        for i, name in enumerate(self.skill_names):
            score = 0.0
            for t, count in q_tf.items():
                if t in self.doc_tf[i]:
                    tf_q = count / q_total
                    tf_d = self.doc_tf[i][t]
                    idf = self.idf.get(t, 1.0)
                    score += tf_q * idf * tf_d * idf
            scores.append((name, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]


def run_trigger_eval_fast(
    skill_name: str,
    trigger_eval_path: Path,
    catalog: dict[str, str],
    top_n: int = 3,
) -> TriggerEvalResult:
    """Run trigger eval in fast mode (TF-IDF)."""
    data = json.loads(trigger_eval_path.read_text(encoding="utf-8"))
    matcher = TfIdfMatcher(catalog)

    result = TriggerEvalResult(
        skill_name=skill_name,
        mode=EvalMode.FAST,
    )

    # should_trigger
    for item in data.get("should_trigger", []):
        query = item["query"]
        matches = matcher.match(query, top_n)
        matched_names = [m[0] for m in matches]
        matched_scores = [m[1] for m in matches]
        result.should_trigger_results.append(TriggerMatch(
            query=query,
            expected_skill=skill_name,
            matched_skills=matched_names,
            scores=matched_scores,
            in_top_n=skill_name in matched_names,
            mode=EvalMode.FAST,
        ))

    # should_not_trigger
    for item in data.get("should_not_trigger", []):
        query = item["query"]
        matches = matcher.match(query, top_n)
        matched_names = [m[0] for m in matches]
        matched_scores = [m[1] for m in matches]
        result.should_not_trigger_results.append(TriggerMatch(
            query=query,
            expected_skill=skill_name,
            matched_skills=matched_names,
            scores=matched_scores,
            in_top_n=skill_name in matched_names,
            mode=EvalMode.FAST,
        ))

    return result


# ---------------------------------------------------------------------------
# Deep mode: Claude-as-judge
# ---------------------------------------------------------------------------

def run_trigger_eval_deep(
    skill_name: str,
    trigger_eval_path: Path,
    catalog: dict[str, str],
    top_n: int = 3,
    model: str = "claude-sonnet-4-5-20250514",
) -> TriggerEvalResult:
    """Run trigger eval in deep mode (Claude-as-judge)."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package required for deep mode. Install: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable required for deep mode", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    data = json.loads(trigger_eval_path.read_text(encoding="utf-8"))

    # Build skill list for the judge
    skill_list = "\n".join(
        f"- **{name}**: {desc[:200]}" for name, desc in sorted(catalog.items())
    )

    result = TriggerEvalResult(
        skill_name=skill_name,
        mode=EvalMode.DEEP,
    )

    all_queries = []
    for item in data.get("should_trigger", []):
        all_queries.append(("should_trigger", item["query"]))
    for item in data.get("should_not_trigger", []):
        all_queries.append(("should_not_trigger", item["query"]))

    # Batch queries for efficiency (one API call per batch of 10)
    batch_size = 10
    for i in range(0, len(all_queries), batch_size):
        batch = all_queries[i:i + batch_size]
        queries_text = "\n".join(f"{j+1}. \"{q[1]}\"" for j, q in enumerate(batch))

        prompt = (
            f"You are evaluating a skill-matching system. Given these available skills:\n\n"
            f"{skill_list}\n\n"
            f"For each query below, return the top {top_n} most relevant skill names "
            f"(just the name field, comma-separated). Return EXACTLY one line per query "
            f"in format: `N. skill1, skill2, skill3`\n\n"
            f"Queries:\n{queries_text}"
        )

        response = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text
        response_lines = [l.strip() for l in response_text.strip().split("\n") if l.strip()]

        for j, (query_type, query) in enumerate(batch):
            matched_names: list[str] = []
            if j < len(response_lines):
                line = re.sub(r'^\d+\.\s*', '', response_lines[j])
                matched_names = [n.strip() for n in line.split(",") if n.strip()][:top_n]

            match = TriggerMatch(
                query=query,
                expected_skill=skill_name,
                matched_skills=matched_names,
                scores=[1.0 / (k + 1) for k in range(len(matched_names))],
                in_top_n=skill_name in matched_names,
                mode=EvalMode.DEEP,
            )

            if query_type == "should_trigger":
                result.should_trigger_results.append(match)
            else:
                result.should_not_trigger_results.append(match)

    return result


# ---------------------------------------------------------------------------
# Discovery and orchestration
# ---------------------------------------------------------------------------

def find_trigger_evals(project_root: Path) -> dict[str, Path]:
    """Find all trigger-eval.json files, keyed by skill name."""
    skills_dir = project_root / "skills"
    result: dict[str, Path] = {}
    for f in skills_dir.rglob("trigger-eval.json"):
        skill_name = f.parent.parent.name
        result[skill_name] = f
    return result


def run_trigger_eval(
    skill_name: str,
    trigger_eval_path: Path,
    catalog: dict[str, str],
    mode: EvalMode = EvalMode.FAST,
    top_n: int = 3,
) -> TriggerEvalResult:
    """Run trigger eval in the specified mode."""
    if mode == EvalMode.FAST:
        return run_trigger_eval_fast(skill_name, trigger_eval_path, catalog, top_n)
    return run_trigger_eval_deep(skill_name, trigger_eval_path, catalog, top_n)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run trigger evals")
    parser.add_argument("--skill", type=str, help="Specific skill to test")
    parser.add_argument("--all", action="store_true", help="Test all skills")
    parser.add_argument(
        "--mode", choices=["fast", "deep"], default="fast",
        help="Matching mode: fast (TF-IDF) or deep (Claude-as-judge)",
    )
    parser.add_argument("--top-n", type=int, default=3, help="Top-N for matching")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    mode = EvalMode(args.mode)
    catalog = build_skill_catalog(args.project_root)
    trigger_evals = find_trigger_evals(args.project_root)

    if args.skill:
        skills_to_test = [args.skill]
    elif args.all:
        skills_to_test = sorted(trigger_evals.keys())
    else:
        print("Specify --skill NAME or --all", file=sys.stderr)
        sys.exit(1)

    all_results: list[TriggerEvalResult] = []
    for skill in skills_to_test:
        if skill not in trigger_evals:
            print(f"SKIP: {skill} — no trigger-eval.json found", file=sys.stderr)
            continue

        result = run_trigger_eval(skill, trigger_evals[skill], catalog, mode, args.top_n)
        all_results.append(result)

        if args.format == "text":
            _print_result(result)

    if args.format == "json":
        import dataclasses
        print(json.dumps(
            [dataclasses.asdict(r) for r in all_results],
            indent=2, ensure_ascii=False, default=str,
        ))

    # Summary
    if len(all_results) > 1 and args.format == "text":
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        total_trg = sum(len(r.should_trigger_results) for r in all_results)
        total_atrg = sum(len(r.should_not_trigger_results) for r in all_results)
        passed_trg = sum(
            sum(1 for m in r.should_trigger_results if m.in_top_n)
            for r in all_results
        )
        passed_atrg = sum(
            sum(1 for m in r.should_not_trigger_results if not m.in_top_n)
            for r in all_results
        )
        avg_acc = sum(r.overall_accuracy for r in all_results) / len(all_results)
        print(f"Skills tested:       {len(all_results)}")
        print(f"Trigger accuracy:    {passed_trg}/{total_trg} ({passed_trg/max(total_trg,1)*100:.1f}%)")
        print(f"Anti-trigger accur:  {passed_atrg}/{total_atrg} ({passed_atrg/max(total_atrg,1)*100:.1f}%)")
        print(f"Average overall:     {avg_acc:.1f}%")


def _print_result(result: TriggerEvalResult) -> None:
    print(f"\n{'=' * 60}")
    print(f"SKILL: {result.skill_name} (mode: {result.mode.value})")
    print(f"{'=' * 60}")

    # should_trigger
    passed = sum(1 for r in result.should_trigger_results if r.in_top_n)
    total = len(result.should_trigger_results)
    print(f"\nShould Trigger: {passed}/{total} ({result.trigger_accuracy:.1f}%)")
    for m in result.should_trigger_results:
        status = "PASS" if m.in_top_n else "FAIL"
        print(f"  [{status}] \"{m.query[:60]}...\"")
        if not m.in_top_n:
            print(f"         Got: {', '.join(m.matched_skills[:3])}")

    # should_not_trigger
    rejected = sum(1 for r in result.should_not_trigger_results if not r.in_top_n)
    total_n = len(result.should_not_trigger_results)
    print(f"\nShould NOT Trigger: {rejected}/{total_n} ({result.anti_trigger_accuracy:.1f}%)")
    for m in result.should_not_trigger_results:
        status = "PASS" if not m.in_top_n else "FAIL"
        print(f"  [{status}] \"{m.query[:60]}...\"")
        if m.in_top_n:
            print(f"         Wrongly matched with score: {m.scores[m.matched_skills.index(result.skill_name)]:.4f}")

    print(f"\nOverall accuracy: {result.overall_accuracy:.1f}%")


if __name__ == "__main__":
    main()
