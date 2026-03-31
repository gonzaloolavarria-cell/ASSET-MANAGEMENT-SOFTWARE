#!/usr/bin/env python3
"""Skill quality auditor for AMS and OR SYSTEM.

Parses all CLAUDE.md skill files, extracts frontmatter, and generates a
quality report covering description length, trigger coverage, and structural
completeness.

Usage:
    python scripts/audit_skills.py [--project-root PATH] [--format json|markdown]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_yaml_frontmatter(text: str) -> dict:
    """Minimal YAML-like frontmatter parser (no PyYAML dependency)."""
    m = _FM_RE.match(text)
    if not m:
        return {}
    raw = m.group(1)
    # Collapse multi-line folded scalars (>)
    lines = raw.split("\n")
    result: dict[str, str] = {}
    current_key: str | None = None
    current_val_lines: list[str] = []

    for line in lines:
        # Top-level key: value
        kv = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if kv and not line.startswith("  "):
            # Flush previous
            if current_key is not None:
                result[current_key] = " ".join(current_val_lines).strip()
            current_key = kv.group(1)
            val = kv.group(2).strip().strip('"').strip("'")
            if val == ">" or val == "|":
                current_val_lines = []
            else:
                current_val_lines = [val] if val else []
        elif current_key is not None:
            current_val_lines.append(line.strip())

    if current_key is not None:
        result[current_key] = " ".join(current_val_lines).strip()

    return result


# ---------------------------------------------------------------------------
# Trigger extraction
# ---------------------------------------------------------------------------

_TRIGGER_EN_RE = re.compile(r"Triggers?\s*EN\s*:\s*(.+?)(?:Triggers?\s*ES|$)", re.IGNORECASE | re.DOTALL)
_TRIGGER_ES_RE = re.compile(r"Triggers?\s*ES\s*:\s*(.+?)$", re.IGNORECASE | re.DOTALL)


def _extract_triggers(description: str) -> tuple[list[str], list[str]]:
    """Extract EN and ES trigger phrases from the description field."""
    en: list[str] = []
    es: list[str] = []

    m_en = _TRIGGER_EN_RE.search(description)
    if m_en:
        en = [t.strip().rstrip(".") for t in m_en.group(1).split(",") if t.strip()]

    m_es = _TRIGGER_ES_RE.search(description)
    if m_es:
        es = [t.strip().rstrip(".") for t in m_es.group(1).split(",") if t.strip()]

    return en, es


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

_EXPECTED_SECTIONS = [
    "Rol y Persona",
    "Intake",
    "Flujo de Ejecuci",  # partial match for Ejecución
    "gica de Decisi",   # partial match for Lógica de Decisión
    "Validaci",          # partial match for Validación
    "Recursos Vinculados",
    "Common Pitfalls",
]


def _detect_sections(body: str) -> list[str]:
    """Return which expected sections are present in the CLAUDE.md body."""
    found = []
    for s in _EXPECTED_SECTIONS:
        if s.lower() in body.lower():
            found.append(s)
    return found


# ---------------------------------------------------------------------------
# Audit result
# ---------------------------------------------------------------------------

@dataclass
class SkillAuditResult:
    name: str
    path: str
    description_length: int = 0
    description_under_1024: bool = True
    has_what_it_does: bool = False
    has_when_to_use: bool = False
    triggers_en_count: int = 0
    triggers_es_count: int = 0
    triggers_en_min5: bool = False
    triggers_es_min5: bool = False
    has_anti_triggers: bool = False
    line_count: int = 0
    under_500_lines: bool = True
    sections_found: list[str] = field(default_factory=list)
    sections_missing: list[str] = field(default_factory=list)
    has_evals_json: bool = False
    has_trigger_eval_json: bool = False
    issues: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        """Quality score 0-100."""
        s = 0
        if self.description_under_1024:
            s += 10
        if self.has_what_it_does:
            s += 10
        if self.has_when_to_use:
            s += 10
        if self.triggers_en_min5:
            s += 10
        if self.triggers_es_min5:
            s += 10
        if self.has_anti_triggers:
            s += 5
        if self.under_500_lines:
            s += 5
        # Sections: up to 20 points (7 sections)
        s += min(20, len(self.sections_found) * 3)
        # Evals: 10 each
        if self.has_evals_json:
            s += 10
        if self.has_trigger_eval_json:
            s += 10
        return min(100, s)


def audit_skill(skill_dir: Path) -> SkillAuditResult:
    """Audit a single skill directory."""
    claude_md = skill_dir / "CLAUDE.md"
    if not claude_md.exists():
        return SkillAuditResult(
            name=skill_dir.name,
            path=str(skill_dir),
            issues=["CLAUDE.md not found"],
        )

    text = claude_md.read_text(encoding="utf-8", errors="replace")
    fm = _parse_yaml_frontmatter(text)
    body = _FM_RE.sub("", text, count=1)

    name = fm.get("name", skill_dir.name)
    desc = fm.get("description", "")

    triggers_en, triggers_es = _extract_triggers(desc)
    sections = _detect_sections(body)
    missing = [s for s in _EXPECTED_SECTIONS if s not in sections]

    lines = text.split("\n")

    result = SkillAuditResult(
        name=name,
        path=str(skill_dir.relative_to(skill_dir.parent.parent) if skill_dir.parent.parent.exists() else skill_dir),
        description_length=len(desc),
        description_under_1024=len(desc) <= 1024,
        has_what_it_does=bool(desc and len(desc) > 20),
        has_when_to_use=any(kw in desc.lower() for kw in ["use this skill", "triggers", "when"]),
        triggers_en_count=len(triggers_en),
        triggers_es_count=len(triggers_es),
        triggers_en_min5=len(triggers_en) >= 5,
        triggers_es_min5=len(triggers_es) >= 5,
        has_anti_triggers="do not use" in desc.lower() or "should not trigger" in desc.lower(),
        line_count=len(lines),
        under_500_lines=len(lines) <= 500,
        sections_found=sections,
        sections_missing=missing,
        has_evals_json=(skill_dir / "evals" / "evals.json").exists(),
        has_trigger_eval_json=(skill_dir / "evals" / "trigger-eval.json").exists(),
    )

    # Collect issues
    if not desc:
        result.issues.append("No description in frontmatter")
    if not result.description_under_1024:
        result.issues.append(f"Description too long: {len(desc)} chars (max 1024)")
    if not result.triggers_en_min5:
        result.issues.append(f"Only {len(triggers_en)} EN triggers (min 5)")
    if not result.triggers_es_min5:
        result.issues.append(f"Only {len(triggers_es)} ES triggers (min 5)")
    if not result.has_anti_triggers:
        result.issues.append("No anti-triggers (Do NOT use for...)")
    if not result.under_500_lines:
        result.issues.append(f"CLAUDE.md has {len(lines)} lines (max 500)")
    for m in missing:
        result.issues.append(f"Missing section: {m}")
    if not result.has_evals_json:
        result.issues.append("Missing evals/evals.json")
    if not result.has_trigger_eval_json:
        result.issues.append("Missing evals/trigger-eval.json")

    return result


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_skills(project_root: Path) -> list[Path]:
    """Find all skill directories (contain CLAUDE.md) under skills/."""
    skills_dir = project_root / "skills"
    if not skills_dir.exists():
        return []
    results = []
    for claude_md in sorted(skills_dir.rglob("CLAUDE.md")):
        # Skip knowledge-base directory
        rel = claude_md.relative_to(skills_dir)
        if str(rel).startswith("00-knowledge-base"):
            continue
        results.append(claude_md.parent)
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _format_markdown(results: list[SkillAuditResult]) -> str:
    lines = [
        "# Skill Quality Audit Report",
        "",
        f"**Total skills:** {len(results)}",
        f"**Average score:** {sum(r.score for r in results) / max(len(results), 1):.0f}/100",
        "",
        "## Summary",
        "",
        "| Skill | Score | Desc Len | EN Trg | ES Trg | Anti-Trg | Lines | Evals | Trigger Evals | Issues |",
        "|-------|-------|----------|--------|--------|----------|-------|-------|---------------|--------|",
    ]
    for r in sorted(results, key=lambda x: x.score):
        lines.append(
            f"| {r.name} | {r.score} | {r.description_length} | {r.triggers_en_count} | "
            f"{r.triggers_es_count} | {'Y' if r.has_anti_triggers else 'N'} | "
            f"{r.line_count} | {'Y' if r.has_evals_json else 'N'} | "
            f"{'Y' if r.has_trigger_eval_json else 'N'} | {len(r.issues)} |"
        )

    lines.extend(["", "## Issues by Skill", ""])
    for r in sorted(results, key=lambda x: x.score):
        if r.issues:
            lines.append(f"### {r.name} (score: {r.score})")
            for issue in r.issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Stats
    lines.extend(["", "## Statistics", ""])
    total = len(results)
    lines.append(f"- Skills with evals.json: {sum(1 for r in results if r.has_evals_json)}/{total}")
    lines.append(f"- Skills with trigger-eval.json: {sum(1 for r in results if r.has_trigger_eval_json)}/{total}")
    lines.append(f"- Skills with anti-triggers: {sum(1 for r in results if r.has_anti_triggers)}/{total}")
    lines.append(f"- Skills under 500 lines: {sum(1 for r in results if r.under_500_lines)}/{total}")
    lines.append(f"- Skills with >=5 EN triggers: {sum(1 for r in results if r.triggers_en_min5)}/{total}")
    lines.append(f"- Skills with >=5 ES triggers: {sum(1 for r in results if r.triggers_es_min5)}/{total}")

    return "\n".join(lines)


def _format_json(results: list[SkillAuditResult]) -> str:
    data = {
        "total_skills": len(results),
        "average_score": round(sum(r.score for r in results) / max(len(results), 1), 1),
        "skills": [
            {**asdict(r), "score": r.score}
            for r in sorted(results, key=lambda x: x.score)
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Audit skill quality")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: cwd)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    skills = discover_skills(args.project_root)
    if not skills:
        print(f"No skills found under {args.project_root / 'skills'}", file=sys.stderr)
        sys.exit(1)

    results = [audit_skill(s) for s in skills]

    if args.format == "markdown":
        output = _format_markdown(results)
    else:
        output = _format_json(results)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
