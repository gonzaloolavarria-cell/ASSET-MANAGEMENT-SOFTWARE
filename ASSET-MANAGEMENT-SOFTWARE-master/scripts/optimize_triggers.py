#!/usr/bin/env python3
"""Trigger description optimizer for AMS and OR SYSTEM skills.

Reads current descriptions and trigger-eval.json data, then generates optimized
descriptions following skill-creator best practices:
  - "Use this skill when:" with numbered contexts
  - "Do NOT use for:" with explicit anti-triggers
  - Under 1024 characters
  - Bilingual trigger coverage integrated naturally

Usage:
    python scripts/optimize_triggers.py --skill assess-criticality [--apply]
    python scripts/optimize_triggers.py --all --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    raw = m.group(1)
    lines = raw.split("\n")
    result: dict[str, str] = {}
    current_key: str | None = None
    current_val_lines: list[str] = []
    for line in lines:
        kv = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if kv and not line.startswith("  "):
            if current_key is not None:
                result[current_key] = " ".join(current_val_lines).strip()
            current_key = kv.group(1)
            val = kv.group(2).strip().strip('"').strip("'")
            current_val_lines = [] if val in (">", "|", "") else [val]
        elif current_key is not None:
            current_val_lines.append(line.strip())
    if current_key is not None:
        result[current_key] = " ".join(current_val_lines).strip()
    return result


# ---------------------------------------------------------------------------
# Trigger analysis
# ---------------------------------------------------------------------------

def _load_trigger_eval(skill_dir: Path) -> dict:
    path = skill_dir / "evals" / "trigger-eval.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_core_themes(queries: list[dict]) -> list[str]:
    """Extract common themes from trigger queries."""
    words: dict[str, int] = {}
    stop_words = {
        "the", "for", "our", "can", "you", "how", "what", "help", "me",
        "with", "this", "that", "from", "need", "want", "run", "show",
        "mill", "sag", "ocp", "pump", "equipment", "del", "para", "los",
        "las", "que", "necesito", "evaluar", "como", "una", "por",
    }
    for q in queries:
        for word in re.findall(r'\b[a-záéíóúñü]{4,}\b', q.get("query", "").lower()):
            if word not in stop_words:
                words[word] = words.get(word, 0) + 1
    # Return top themes
    sorted_words = sorted(words.items(), key=lambda x: x[1], reverse=True)
    return [w for w, c in sorted_words[:10] if c >= 2]


def _extract_anti_trigger_skills(should_not: list[dict]) -> list[str]:
    """Extract skill names mentioned in should_not_trigger reasons."""
    skills = []
    for item in should_not:
        reason = item.get("reason", "")
        # Look for "is X skill" or "use X" patterns
        m = re.search(r'is\s+([\w-]+)\s+skill', reason, re.I)
        if m:
            skills.append(m.group(1))
        m = re.search(r'use\s+([\w-]+)', reason, re.I)
        if m and m.group(1) not in ("this", "the"):
            skills.append(m.group(1))
    return list(dict.fromkeys(skills))


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def optimize_description(
    skill_name: str,
    current_desc: str,
    trigger_data: dict,
) -> str:
    """Generate an optimized description following skill-creator best practices."""
    should_trigger = trigger_data.get("should_trigger", [])
    should_not = trigger_data.get("should_not_trigger", [])

    themes = _extract_core_themes(should_trigger)
    anti_skills = _extract_anti_trigger_skills(should_not)

    # Extract the core "what it does" from current description
    # Remove old trigger lists
    core = re.sub(r'Triggers?\s*(EN|ES)\s*:.*', '', current_desc, flags=re.I | re.DOTALL).strip()
    # Limit core to ~300 chars
    if len(core) > 300:
        core = core[:300].rsplit(" ", 1)[0] + "."

    # Build "Use this skill when:" section
    when_items = []
    for theme in themes[:4]:
        when_items.append(theme.replace("-", " "))
    # Ensure skill name concepts are included
    name_words = skill_name.replace("-", " ").split()
    for w in name_words:
        if w not in " ".join(when_items) and len(w) > 3:
            when_items.append(w)

    when_text = ", ".join(f"({i+1}) {item}" for i, item in enumerate(when_items[:5]))

    # Build "Do NOT use for:" section
    anti_text = ""
    if anti_skills:
        anti_items = [f"{s.replace('-', ' ')} (use {s})" for s in anti_skills[:3]]
        anti_text = f" Do NOT use for: {'; '.join(anti_items)}."

    # Compose optimized description
    optimized = f"{core} Use this skill when: {when_text}.{anti_text}"

    # Enforce 1024 char limit
    if len(optimized) > 1024:
        # Trim anti-triggers first
        optimized = f"{core} Use this skill when: {when_text}."
    if len(optimized) > 1024:
        optimized = optimized[:1020] + "..."

    return optimized


def apply_optimization(skill_dir: Path, new_desc: str) -> None:
    """Apply optimized description to CLAUDE.md frontmatter."""
    claude_md = skill_dir / "CLAUDE.md"
    text = claude_md.read_text(encoding="utf-8")

    fm = _parse_frontmatter(text)
    old_name = fm.get("name", skill_dir.name)

    # Rebuild frontmatter with new description
    new_fm = f'---\nname: {old_name}\ndescription: >\n'
    # Wrap description at ~80 chars
    words = new_desc.split()
    line = "  "
    for word in words:
        if len(line) + len(word) + 1 > 80:
            new_fm += line.rstrip() + "\n"
            line = "  " + word + " "
        else:
            line += word + " "
    new_fm += line.rstrip() + "\n---"

    # Replace old frontmatter
    new_text = _FM_RE.sub(new_fm, text, count=1)
    claude_md.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_skills(project_root: Path) -> list[Path]:
    skills_dir = project_root / "skills"
    results = []
    for claude_md in sorted(skills_dir.rglob("CLAUDE.md")):
        rel = claude_md.relative_to(skills_dir)
        if str(rel).startswith("00-knowledge-base"):
            continue
        results.append(claude_md.parent)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize trigger descriptions")
    parser.add_argument("--skill", type=str, help="Specific skill")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Apply changes to CLAUDE.md (default: dry-run)")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    skills = discover_skills(args.project_root)

    if args.skill:
        skills = [s for s in skills if s.name == args.skill]
    if not args.skill and not args.all:
        print("Specify --skill NAME or --all", file=sys.stderr)
        sys.exit(1)

    for skill_dir in skills:
        claude_md = skill_dir / "CLAUDE.md"
        text = claude_md.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        current_desc = fm.get("description", "")
        trigger_data = _load_trigger_eval(skill_dir)

        if not trigger_data:
            print(f"SKIP: {skill_dir.name} — no trigger-eval.json")
            continue

        optimized = optimize_description(skill_dir.name, current_desc, trigger_data)

        print(f"\n{'=' * 60}")
        print(f"SKILL: {skill_dir.name}")
        print(f"{'=' * 60}")
        print(f"CURRENT ({len(current_desc)} chars):")
        print(f"  {current_desc[:200]}...")
        print(f"\nOPTIMIZED ({len(optimized)} chars):")
        print(f"  {optimized[:200]}...")

        if args.apply:
            apply_optimization(skill_dir, optimized)
            print(f"  -> APPLIED to {claude_md}")
        else:
            print(f"  -> DRY-RUN (use --apply to write)")


if __name__ == "__main__":
    main()
