"""Main workflow engine for the 4-milestone strategy development process.

Coordinates the OrchestratorAgent through 4 milestones with human
approval gates between each. This is the top-level entry point
for running a complete strategy development session.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Callable

from anthropic import Anthropic

logger = logging.getLogger(__name__)

from agents.definitions.orchestrator import create_orchestrator, OrchestratorAgent
from agents.orchestration.session_state import SessionState
from agents.orchestration.milestones import (
    MilestoneGate,
    MilestoneStatus,
    ValidationSummary,
    create_milestone_gates,
)
from agents.tool_wrappers.registry import call_tool


# Type alias for human approval callback
# Receives: milestone number, gate summary text
# Returns: ("approve", feedback) | ("modify", feedback) | ("reject", feedback)
HumanApprovalFn = Callable[[int, str], tuple[str, str]]


def _run_validation(session: SessionState) -> ValidationSummary:
    """Run full validation on accumulated session entities."""
    validation_input = session.get_validation_input()
    if not validation_input:
        return ValidationSummary()

    result_json = call_tool("run_full_validation", {"input_json": json.dumps(validation_input)})
    results = json.loads(result_json)

    # call_tool may return {"error": "..."} instead of a list on failure
    if isinstance(results, dict):
        if "error" in results:
            logger.warning("Validation tool returned error: %s", results["error"])
            return ValidationSummary(errors=0, warnings=1, info=0, details=[results])
        results = [results]

    errors = sum(1 for r in results if isinstance(r, dict) and r.get("severity") == "ERROR")
    warnings = sum(1 for r in results if isinstance(r, dict) and r.get("severity") == "WARNING")
    info = sum(1 for r in results if isinstance(r, dict) and r.get("severity") == "INFO")

    return ValidationSummary(
        errors=errors,
        warnings=warnings,
        info=info,
        details=results,
    )


def _run_quality_scoring(session: SessionState, milestone: int, pass_threshold: float = 91.0) -> dict:
    """Run quality scoring on session entities for the current milestone."""
    from tools.engines.quality_score_engine import QualityScoreEngine

    try:
        report = QualityScoreEngine.score_session(
            session_entities=session.entities,
            milestone=milestone,
            session_id=session.session_id,
            pass_threshold=pass_threshold,
        )
        report_dict = report.model_dump()

        # Link quality_score_id to matching deliverables
        _link_quality_scores_to_deliverables(session, report_dict, milestone)

        return report_dict
    except Exception:
        logger.debug("Quality scoring failed (non-critical)", exc_info=True)
        return {}


def _link_quality_scores_to_deliverables(
    session: SessionState, quality_report: dict, milestone: int
) -> None:
    """Match deliverable_scores from quality report to session deliverables by category."""
    try:
        from tools.engines.deliverable_tracking_engine import STAGE_TO_CATEGORY

        deliverables = session.deliverables
        if not deliverables:
            return

        for ds in quality_report.get("deliverable_scores", []):
            score_id = ds.get("score_id", "")
            d_type = ds.get("deliverable_type", "").upper()

            # Find matching deliverable by milestone + category
            for d in deliverables:
                if d.get("milestone") == milestone and d.get("category", "").upper() == d_type:
                    d["quality_score_id"] = score_id
                    break
    except Exception:
        logger.debug("Failed to link quality scores to deliverables (non-critical)", exc_info=True)


def _format_gate_summary(
    milestone: MilestoneGate,
    session: SessionState,
    validation: ValidationSummary,
    quality_report: dict | None = None,
) -> str:
    """Format the summary text presented to the human at a gate."""
    counts = session.get_entity_counts()
    lines = [
        f"=== Milestone {milestone.number}: {milestone.name} ===",
        f"Description: {milestone.description}",
        "",
        "Entity counts:",
    ]
    for entity, count in counts.items():
        if isinstance(count, bool):
            lines.append(f"  {entity}: {'Yes' if count else 'No'}")
        elif count > 0:
            lines.append(f"  {entity}: {count}")

    lines.append("")
    lines.append(f"Validation: {validation.errors} errors, {validation.warnings} warnings, {validation.info} info")

    if validation.has_errors:
        lines.append("")
        lines.append("ERRORS (must fix before approval):")
        for detail in validation.details:
            if detail.get("severity") == "ERROR":
                lines.append(f"  - [{detail.get('rule_id', '?')}] {detail.get('message', '?')}")

    if validation.warnings > 0:
        lines.append("")
        lines.append("WARNINGS (review recommended):")
        for detail in validation.details:
            if detail.get("severity") == "WARNING":
                lines.append(f"  - [{detail.get('rule_id', '?')}] {detail.get('message', '?')}")

    # Quality score section
    if quality_report:
        lines.append("")
        overall = quality_report.get("overall_score", 0)
        grade = quality_report.get("overall_grade", "?")
        threshold = quality_report.get("pass_threshold", 91.0)
        passes = quality_report.get("passes_gate", False)
        lines.append(
            f"Quality Score: {overall}% (Grade: {grade}) — "
            f"Threshold: {threshold}% — {'PASS' if passes else 'FAIL'}"
        )
        for ds in quality_report.get("deliverable_scores", []):
            lines.append(
                f"  {ds.get('deliverable_type', '?')}: "
                f"{ds.get('composite_score', 0)}% ({ds.get('grade', '?')})"
            )

    lines.append("")
    lines.append("Action: APPROVE / MODIFY / REJECT")
    return "\n".join(lines)


def _extract_entities_from_response(response: str) -> dict:
    """Extract a JSON entity dict from an agent text response.

    Tries, in order:
    1. ```json ... ``` fenced block (all matches, picks the largest valid dict)
    2. Incremental JSONDecoder scan for the first valid top-level object
    3. The entire response as raw JSON

    Returns empty dict if no valid JSON is found.
    """
    # 1. All JSON fenced blocks — pick the largest valid dict
    fenced = re.findall(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    best: dict = {}
    for block in fenced:
        try:
            result = json.loads(block)
            if isinstance(result, dict) and len(str(result)) > len(str(best)):
                best = result
        except json.JSONDecodeError:
            pass
    if best:
        return best

    # 2. Incremental JSONDecoder — find valid JSON objects by scanning for '{'
    decoder = json.JSONDecoder()
    for i, ch in enumerate(response):
        if ch == "{":
            try:
                obj, end = decoder.raw_decode(response, i)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue

    # 3. Entire response
    try:
        result = json.loads(response.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    logger.warning("Could not extract JSON entities from agent response (len=%d)", len(response))
    return {}


def _extract_entities_from_tool_results(agent, entity_keys: list[str]) -> dict:
    """Extract entity data from an agent's tool call history.

    When agents use tools (build_hierarchy_from_vendor, assess_criticality, etc.),
    the structured data lives in the tool results, not the final text response.
    This scans the agent's history for tool results containing the expected entity keys.

    Args:
        agent: The Agent instance whose history to scan.
        entity_keys: Entity keys to look for (e.g. ["hierarchy_nodes", "criticality_assessments"]).

    Returns:
        Dict mapping entity_key → list of entity dicts found in tool results.
    """
    collected: dict[str, list] = {}

    for turn in reversed(agent.history):
        for tr in getattr(turn, "tool_results", []):
            result_str = tr.get("result", "")
            if not result_str or not isinstance(result_str, str):
                continue
            try:
                parsed = json.loads(result_str)
            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(parsed, dict):
                # Tool returned a dict — check if it contains entity arrays
                for key in entity_keys:
                    if key in parsed and isinstance(parsed[key], list):
                        collected.setdefault(key, []).extend(parsed[key])
                # Also check if the dict itself IS an entity (single item)
                # e.g. a single hierarchy node returned by a tool
                for key in entity_keys:
                    singular = key.rstrip("s")  # "hierarchy_nodes" -> "hierarchy_node"
                    if singular in parsed and isinstance(parsed[singular], dict):
                        collected.setdefault(key, []).append(parsed[singular])
                # Check if the dict looks like a single entity (has expected fields)
                # Use negative-exclusion checks + break to prevent cross-contamination
                if not any(k in parsed for k in entity_keys):
                    for key in entity_keys:
                        if key == "hierarchy_nodes" and "node_id" in parsed and "assessment_id" not in parsed:
                            collected.setdefault(key, []).append(parsed)
                            break
                        elif key == "criticality_assessments" and "assessment_id" in parsed:
                            collected.setdefault(key, []).append(parsed)
                            break
                        elif key == "functions" and "function_id" in parsed and "failure_id" not in parsed:
                            collected.setdefault(key, []).append(parsed)
                            break
                        elif key == "functional_failures" and "failure_id" in parsed:
                            collected.setdefault(key, []).append(parsed)
                            break
                        elif key == "failure_modes" and ("fm_id" in parsed or "failure_mode_id" in parsed or ("mechanism" in parsed and "cause" in parsed)):
                            collected.setdefault(key, []).append(parsed)
                            break
                        elif key == "maintenance_tasks" and "task_id" in parsed and "wp_id" not in parsed and "wp_code" not in parsed:
                            collected.setdefault(key, []).append(parsed)
                            break
                        elif key == "work_packages" and ("wp_id" in parsed or "wp_code" in parsed or "work_package_id" in parsed):
                            collected.setdefault(key, []).append(parsed)
                            break

            elif isinstance(parsed, list):
                # Tool returned a list — check if items look like entities
                # Use negative-exclusion checks + break to prevent cross-contamination
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    for key in entity_keys:
                        if key == "hierarchy_nodes" and "node_id" in item and "assessment_id" not in item:
                            collected.setdefault(key, []).append(item)
                            break
                        elif key == "criticality_assessments" and "assessment_id" in item:
                            collected.setdefault(key, []).append(item)
                            break
                        elif key == "functions" and "function_id" in item and "failure_id" not in item:
                            collected.setdefault(key, []).append(item)
                            break
                        elif key == "functional_failures" and "failure_id" in item:
                            collected.setdefault(key, []).append(item)
                            break
                        elif key == "failure_modes" and ("fm_id" in item or "failure_mode_id" in item or ("mechanism" in item and "cause" in item)):
                            collected.setdefault(key, []).append(item)
                            break
                        elif key == "maintenance_tasks" and "task_id" in item and "wp_id" not in item and "wp_code" not in item:
                            collected.setdefault(key, []).append(item)
                            break
                        elif key == "work_packages" and ("wp_id" in item or "wp_code" in item or "work_package_id" in item):
                            collected.setdefault(key, []).append(item)
                            break

    if collected:
        logger.info("Extracted entities from tool results: %s",
                     {k: len(v) for k, v in collected.items()})
    return collected


def _ensure_ancestor_nodes(
    nodes: list[dict], plant_code: str, equipment_tag: str,
) -> list[dict]:
    """Ensure L1-L3 ancestor nodes exist for a hierarchy.

    build_from_vendor only creates L4+ nodes. The template xlsx
    (and quality scorer) expect L1 (plant), L2 (area), L3 (system)
    ancestors. This generates synthetic ones if missing, and wires
    the parent_node_id chain.
    """
    # Check what levels exist
    level_set: set[int] = set()
    for n in nodes:
        lvl = n.get("level")
        if isinstance(lvl, int):
            level_set.add(lvl)
        elif isinstance(lvl, str):
            for ch in str(lvl):
                if ch.isdigit():
                    level_set.add(int(ch))
                    break

    if {1, 2, 3}.issubset(level_set):
        return nodes  # Already has L1-L3

    # Parse plant_code and equipment_tag for node names
    area_code = "GRD"  # Default grinding area
    # Find any L4 equipment node to extract area from its tag
    for n in nodes:
        if n.get("level") == 4 and n.get("tag"):
            tag = n["tag"]
            parts = tag.split("-")
            if parts:
                area_code = parts[0]
            break

    added: list[dict] = []

    # Synthetic L1 (plant)
    plant_node_id = f"SYN-L1-{plant_code}"
    if 1 not in level_set:
        added.append({
            "node_id": plant_node_id,
            "node_type": "PLANT",
            "name": f"{plant_code} Plant",
            "name_fr": f"Usine {plant_code}",
            "code": plant_code,
            "tag": plant_code,
            "level": 1,
            "parent_node_id": None,
            "status": "ACTIVE",
        })

    # Synthetic L2 (area)
    area_node_id = f"SYN-L2-{area_code}"
    if 2 not in level_set:
        added.append({
            "node_id": area_node_id,
            "node_type": "AREA",
            "name": f"{area_code} Area",
            "name_fr": f"Zone {area_code}",
            "code": area_code,
            "tag": area_code,
            "level": 2,
            "parent_node_id": plant_node_id,
            "status": "ACTIVE",
        })

    # Synthetic L3 (system)
    system_node_id = f"SYN-L3-{area_code}-SYS"
    if 3 not in level_set:
        # Use equipment description for system name
        sys_name = equipment_tag.split(" ")[0] if equipment_tag else "Main"
        added.append({
            "node_id": system_node_id,
            "node_type": "SYSTEM",
            "name": f"{sys_name} System",
            "name_fr": f"Système {sys_name}",
            "code": f"{area_code}-SYS",
            "tag": f"{area_code}-SYS",
            "level": 3,
            "parent_node_id": area_node_id,
            "status": "ACTIVE",
        })

    if added:
        # Wire orphan L4 equipment nodes to the L3 system
        for n in nodes:
            if n.get("level") == 4 and not n.get("parent_node_id"):
                n["parent_node_id"] = system_node_id

        logger.info("Added %d synthetic ancestor nodes (L1-L3)", len(added))
        return added + nodes

    return nodes


# ---------------------------------------------------------------------------
# Post-extraction enrichment: synthesise missing entities from what we have
# ---------------------------------------------------------------------------

def _enrich_m2_entities(
    entities: dict,
    hierarchy_nodes: list[dict],
    agent=None,
) -> dict:
    """Enrich M2 entities so the quality scorer sees complete FMECA data.

    Addresses three gaps that cause low quality scores:

    1. **Missing functions / functional_failures**: If the agent didn't return
       them, synthesise one function + one functional failure per MI node.
    2. **Incomplete failure_modes**: Fill in ``failure_mode_id``, ``what``,
       ``functional_failure_id``, ``is_hidden`` from existing data.
    3. **Missing RCM fields**: Harvest ``strategy_type`` and
       ``failure_consequence`` from ``rcm_decide`` tool results in the agent's
       conversation history and merge them into the corresponding failure modes.
    """
    failure_modes = entities.get("failure_modes", [])

    # --- 1. Synthesise functions & functional_failures if empty -----------
    functions = entities.get("functions", [])
    functional_failures = entities.get("functional_failures", [])

    mi_nodes = [
        n for n in hierarchy_nodes
        if n.get("node_type") == "MAINTAINABLE_ITEM"
        or n.get("level") == 4
        or (isinstance(n.get("level"), str) and "4" in str(n.get("level")))
    ]

    if not functions and mi_nodes:
        logger.info("M2-enrich: synthesising %d functions from MI nodes", len(mi_nodes))
        for i, mi in enumerate(mi_nodes, 1):
            nid = mi.get("node_id", f"MI-{i}")
            name = mi.get("name") or mi.get("equipment_description") or mi.get("tag") or nid
            func = {
                "function_id": f"FN-{i:03d}",
                "node_id": nid,
                "function_type": "PRIMARY",
                "description": f"Perform intended function of {name}",
                "description_fr": f"Réaliser la fonction prévue de {name}",
            }
            functions.append(func)
        entities["functions"] = functions

    if not functional_failures and functions:
        logger.info("M2-enrich: synthesising %d functional_failures", len(functions))
        for i, func in enumerate(functions, 1):
            ff = {
                "failure_id": f"FF-{i:03d}",
                "function_id": func["function_id"],
                "failure_type": "TOTAL",
                "description": f"Unable to {func.get('description', '').lower()}",
                "description_fr": f"Incapable de {func.get('description_fr', '').lower()}",
            }
            functional_failures.append(ff)
        entities["functional_failures"] = functional_failures

    # Build lookup: node_id → function_id → failure_id for traceability
    node_to_func = {f["node_id"]: f["function_id"] for f in functions if "node_id" in f}
    func_to_ff = {ff["function_id"]: ff["failure_id"] for ff in functional_failures if "function_id" in ff}

    # --- 2. Harvest RCM results from agent tool history -------------------
    rcm_results: list[dict] = []
    if agent is not None:
        for turn in reversed(getattr(agent, "history", [])):
            for tr in getattr(turn, "tool_results", []):
                tool_name = tr.get("tool_name", "")
                if tool_name != "rcm_decide":
                    continue
                result_str = tr.get("result", "")
                if not result_str:
                    continue
                try:
                    parsed = json.loads(result_str)
                    if isinstance(parsed, dict) and "strategy_type" in parsed:
                        # Try to pair with the tool call input to get the FM context
                        rcm_results.append(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass
        if rcm_results:
            logger.info("M2-enrich: harvested %d rcm_decide results from agent history", len(rcm_results))

    # --- 3. Enrich each failure mode --------------------------------------
    rcm_idx = 0
    for i, fm in enumerate(failure_modes):
        # failure_mode_id
        if not fm.get("failure_mode_id"):
            fm["failure_mode_id"] = fm.get("fm_id") or f"FM-{i + 1:03d}"

        # 'what' description
        if not fm.get("what"):
            mechanism = fm.get("mechanism", "Unknown mechanism")
            cause = fm.get("cause", "unknown cause")
            fm["what"] = f"{mechanism.replace('_', ' ').title()} due to {cause.replace('_', ' ').lower()}"

        # Merge RCM results (strategy_type, failure_consequence)
        if rcm_results and rcm_idx < len(rcm_results):
            rcm = rcm_results[rcm_idx]
            if not fm.get("strategy_type"):
                st = rcm.get("strategy_type", "")
                # Normalise: RCM engine returns e.g. "CONDITION_BASED_MAINTENANCE" or "StrategyType.CONDITION_BASED"
                st = st.replace("StrategyType.", "").replace("_MAINTENANCE", "")
                fm["strategy_type"] = st
            if not fm.get("failure_consequence"):
                fc = rcm.get("path", "")
                # Normalise: RCM engine returns e.g. "RCMPath.EVIDENT_OPERATIONAL" or "EVIDENT_OPERATIONAL"
                fc = fc.replace("RCMPath.", "")
                fm["failure_consequence"] = fc
            rcm_idx += 1

        # is_hidden from failure_consequence
        if fm.get("is_hidden") is None and fm.get("failure_consequence"):
            fm["is_hidden"] = fm["failure_consequence"].startswith("HIDDEN")

        # Traceability: link FM → functional_failure → function
        if not fm.get("functional_failure_id"):
            # Try to find via node_id if present
            node_id = fm.get("node_id")
            if node_id and node_id in node_to_func:
                func_id = node_to_func[node_id]
                fm["functional_failure_id"] = func_to_ff.get(func_id)
            elif functional_failures:
                # Assign round-robin if no node_id link
                ff_idx = i % len(functional_failures)
                fm["functional_failure_id"] = functional_failures[ff_idx]["failure_id"]

    entities["failure_modes"] = failure_modes
    logger.info(
        "M2-enrich: final counts — functions=%d, functional_failures=%d, "
        "failure_modes=%d (with strategy_type=%d)",
        len(functions), len(functional_failures), len(failure_modes),
        sum(1 for fm in failure_modes if fm.get("strategy_type")),
    )
    return entities


def _enrich_m3_entities(entities: dict, failure_modes: list[dict]) -> dict:
    """Enrich M3 entities: ensure tasks reference valid FM IDs and have required fields."""
    tasks = entities.get("maintenance_tasks", [])
    fm_ids = {fm.get("failure_mode_id") or fm.get("fm_id") for fm in failure_modes}

    for i, task in enumerate(tasks):
        if not task.get("task_id"):
            task["task_id"] = f"TSK-{i + 1:03d}"

        # Ensure T-16 rule: REPLACE tasks have material_required=True
        task_type = (task.get("task_type") or task.get("type") or "").upper()
        if task_type == "REPLACE" and not task.get("material_required"):
            task["material_required"] = True

        # Ensure description ≤ 72 chars
        desc = task.get("description", "")
        if len(desc) > 72:
            task["description"] = desc[:69] + "..."

    work_packages = entities.get("work_packages", [])
    for i, wp in enumerate(work_packages):
        if not wp.get("wp_id"):
            wp["wp_id"] = wp.get("wp_code") or wp.get("work_package_id") or f"WP-{i + 1:03d}"

    entities["maintenance_tasks"] = tasks
    entities["work_packages"] = work_packages
    return entities


def _sanitize_entities(entities: dict, entity_keys: list[str]) -> dict:
    """Post-extraction sanitization: remove cross-contaminated entities.

    Even after careful extraction, the agent's JSON response may mix entity
    types (e.g. assessments appearing in hierarchy_nodes because both have
    node_id). This function applies definitive classification rules.
    """
    # M1: hierarchy_nodes vs criticality_assessments
    if "hierarchy_nodes" in entities:
        raw = entities["hierarchy_nodes"]
        if isinstance(raw, list):
            clean_nodes = []
            stray_assessments = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                if "assessment_id" in item:
                    stray_assessments.append(item)
                else:
                    clean_nodes.append(item)
            entities["hierarchy_nodes"] = clean_nodes
            if stray_assessments:
                logger.info("Sanitized %d assessments out of hierarchy_nodes", len(stray_assessments))
                ca = entities.setdefault("criticality_assessments", [])
                # Deduplicate by assessment_id
                existing_ids = {a.get("assessment_id") for a in ca if isinstance(a, dict)}
                for a in stray_assessments:
                    if a.get("assessment_id") not in existing_ids:
                        ca.append(a)
                        existing_ids.add(a.get("assessment_id"))

    # M2: functions vs functional_failures
    if "functions" in entities:
        raw = entities["functions"]
        if isinstance(raw, list):
            clean_funcs = []
            stray_failures = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                if "failure_id" in item:
                    stray_failures.append(item)
                else:
                    clean_funcs.append(item)
            entities["functions"] = clean_funcs
            if stray_failures:
                logger.info("Sanitized %d failures out of functions", len(stray_failures))
                ff = entities.setdefault("functional_failures", [])
                existing_ids = {f.get("failure_id") for f in ff if isinstance(f, dict)}
                for f in stray_failures:
                    if f.get("failure_id") not in existing_ids:
                        ff.append(f)
                        existing_ids.add(f.get("failure_id"))

    # M3: maintenance_tasks vs work_packages
    if "maintenance_tasks" in entities:
        raw = entities["maintenance_tasks"]
        if isinstance(raw, list):
            clean_tasks = []
            stray_wps = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                if "wp_id" in item or "wp_code" in item or "work_package_id" in item:
                    stray_wps.append(item)
                else:
                    clean_tasks.append(item)
            entities["maintenance_tasks"] = clean_tasks
            if stray_wps:
                logger.info("Sanitized %d work_packages out of maintenance_tasks", len(stray_wps))
                wp = entities.setdefault("work_packages", [])
                existing_ids = {w.get("wp_id", w.get("wp_code")) for w in wp if isinstance(w, dict)}
                for w in stray_wps:
                    wid = w.get("wp_id", w.get("wp_code"))
                    if wid not in existing_ids:
                        wp.append(w)
                        existing_ids.add(wid)

    return entities


class MaxRetriesExceeded(Exception):
    """Raised when a milestone exceeds max modify retries."""


class StrategyWorkflow:
    """Orchestrates a complete strategy development session.

    Usage:
        def human_gate(milestone_num, summary):
            print(summary)
            action = input("Action [approve/modify/reject]: ")
            feedback = input("Feedback: ")
            return (action, feedback)

        workflow = StrategyWorkflow(human_approval_fn=human_gate)
        result = workflow.run("SAG Mill 001", plant_code="OCP-JFC")
    """

    def __init__(
        self,
        human_approval_fn: HumanApprovalFn,
        client: Anthropic | None = None,
        strict_validation: bool = True,
        max_modify_retries: int = 5,
        checkpoint_dir: str | None = None,
        client_slug: str = "",
        project_slug: str = "",
        quality_threshold: float = 91.0,
    ):
        self.human_approval_fn = human_approval_fn
        # Auto-create Anthropic client from environment if not provided
        if client is None:
            client = Anthropic()  # reads ANTHROPIC_API_KEY from env automatically
        self.orchestrator: OrchestratorAgent = create_orchestrator(client=client)
        self.session = SessionState(
            session_id=str(uuid.uuid4()),
            client_slug=client_slug,
            project_slug=project_slug,
        )
        self.milestones = create_milestone_gates()
        self.strict_validation = strict_validation
        self.max_modify_retries = max_modify_retries
        self.checkpoint_dir = checkpoint_dir
        self._quality_threshold = quality_threshold

        # Resolve memory directory for client memory learning
        self._memory_dir: Path | None = None
        if client_slug and project_slug:
            try:
                from agents._shared.paths import get_memory_dir
                mem = get_memory_dir(client_slug, project_slug)
                if mem.is_dir():
                    self._memory_dir = mem
            except Exception:
                logger.debug("Memory dir resolution failed (non-critical)", exc_info=True)

    def run(self, equipment_description: str, plant_code: str = "OCP") -> SessionState:
        """Run the full 4-milestone workflow.

        Args:
            equipment_description: Equipment to develop strategy for.
            plant_code: SAP plant code.

        Returns:
            Final session state with all accumulated entities.
        """
        self.session.equipment_tag = equipment_description
        self.session.plant_code = plant_code

        for gate in self.milestones:
            self._execute_milestone(gate)

            if gate.status == MilestoneStatus.REJECTED:
                break

        return self.session

    def _execute_milestone(self, gate: MilestoneGate) -> None:
        """Execute a single milestone with agent delegation and human gate.

        Uses an iterative loop instead of recursion for the modify path.
        Raises MaxRetriesExceeded if the human requests too many modifications.

        Specialist agents are called directly via orchestrator.delegate() for
        each milestone, then entity outputs are parsed and written to session.
        """
        for _attempt in range(self.max_modify_retries + 1):
            # Only call start() when PENDING (first attempt).
            # After modify(), status is already IN_PROGRESS.
            if gate.status == MilestoneStatus.PENDING:
                gate.start()

            instruction = self._build_milestone_instruction(gate)
            response = self._run_milestone_agents(gate)

            self.session.record_interaction(
                agent_type="orchestrator",
                milestone=gate.number,
                instruction=instruction,
                response_summary=response[:500],
            )

            # Auto-checkpoint after each agent interaction
            self._auto_checkpoint()

            validation = _run_validation(self.session)
            quality_report = _run_quality_scoring(
                self.session, gate.number, self._quality_threshold
            )
            gate.present(validation)

            summary = _format_gate_summary(
                gate, self.session, validation, quality_report=quality_report
            )
            action, feedback = self.human_approval_fn(gate.number, summary)

            if action == "approve":
                if validation.has_errors:
                    if self.strict_validation:
                        gate.modify("Cannot approve: validation has errors")
                        continue
                    logger.warning(
                        "Milestone %d approved with %d validation errors (strict_validation=False)",
                        gate.number,
                        validation.errors,
                    )
                gate.approve(feedback)
                # Save confirmed pattern to memory
                self._save_memory_learning(feedback, "approve", gate.number, _attempt)
                # Update execution plan checkboxes for this milestone
                self._update_execution_plan(gate.number)
                # Generate populated template xlsx deliverables (registers deliverables)
                self._write_template_deliverables(gate.number)
                # M4 approved: serialize SAP package to .xlsx (G-20)
                if gate.number == 4:
                    self._write_sap_xlsx()
                # Transition any DRAFT/IN_PROGRESS deliverables to SUBMITTED
                self._update_deliverable_status(gate.number)
                # Re-link quality scores now that deliverables exist
                if quality_report:
                    _link_quality_scores_to_deliverables(
                        self.session, quality_report, gate.number
                    )
                # Save checkpoint: explicit dir > client project dir > skip
                from agents.orchestration.checkpoint import save_checkpoint
                if self.checkpoint_dir:
                    from pathlib import Path
                    save_checkpoint(self.session, gate.number, Path(self.checkpoint_dir))
                elif self.session.client_slug and self.session.project_slug:
                    save_checkpoint(self.session, gate.number)
                return
            elif action == "modify":
                # Save deviation to memory before retrying
                self._save_memory_learning(feedback, "modify", gate.number, _attempt)
                gate.modify(feedback)
                continue
            elif action == "reject":
                gate.reject(feedback)
                return

        raise MaxRetriesExceeded(
            f"Milestone {gate.number} exceeded {self.max_modify_retries} modify attempts"
        )

    def _write_sap_xlsx(self) -> None:
        """Serialize the M4 SAP upload package to an .xlsx file (G-20).

        Output path: sap_export/{session_id}_sap_upload.xlsx
        Path is stored in session.sap_upload_package['xlsx_path'] for UI access.
        Non-critical: logs and continues on failure.
        """
        pkg_dict = self.session.sap_upload_package
        if not pkg_dict:
            logger.debug("No SAP upload package in session — skipping xlsx write")
            return

        try:
            from pathlib import Path as _Path
            from tools.engines.sap_export_engine import SAPExportEngine
            from tools.models.schemas import SAPUploadPackage

            pkg = SAPUploadPackage(**pkg_dict)
            out_dir = _Path("sap_export")
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f"{self.session.session_id}_sap_upload.xlsx"
            SAPExportEngine.write_to_xlsx(pkg, out_path)

            # Store path back in session for downstream access
            self.session.sap_upload_package["xlsx_path"] = str(out_path)
            logger.info("SAP xlsx written to: %s", out_path)
            print(f"\n[SAP Export] Package written to: {out_path}")

            # Register SAP deliverable in session
            try:
                from datetime import datetime, timezone
                import uuid
                from tools.engines.deliverable_tracking_engine import DEFAULT_HOURS
                from tools.models.schemas import DeliverableCategory
                self.session.write_entities("deliverables", [{
                    "deliverable_id": str(uuid.uuid4()),
                    "name": "SAP Upload Package",
                    "name_fr": "Package SAP PM",
                    "category": "SAP_UPLOAD",
                    "milestone": 4,
                    "status": "SUBMITTED",
                    "estimated_hours": DEFAULT_HOURS.get(DeliverableCategory.SAP_UPLOAD, 2.0),
                    "artifact_paths": [str(out_path)],
                    "client_slug": self.session.client_slug or "",
                    "project_slug": self.session.project_slug or "",
                    "assigned_agent": "orchestrator",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                }], "orchestrator")
            except Exception:
                logger.debug("Failed to register SAP deliverable (non-critical)", exc_info=True)
        except Exception:
            logger.warning("SAP xlsx serialization failed (non-critical)", exc_info=True)

    def _write_template_deliverables(self, milestone_number: int) -> None:
        """Generate populated AMS template xlsx files for the approved milestone.

        Output directory: deliverables/{session_id}/
        Non-critical: logs and continues on failure.
        """
        try:
            from pathlib import Path as _Path
            from tools.engines.template_population_engine import TemplatePopulationEngine

            out_dir = _Path("deliverables") / self.session.session_id
            results = TemplatePopulationEngine.populate_all(
                session_entities=self.session.entities,
                output_dir=out_dir,
                plant_code=self.session.plant_code,
                sap_package=self.session.sap_upload_package,
            )
            if results:
                print(f"\n[Deliverables] M{milestone_number}: {len(results)} templates written to {out_dir}/")
                for name in sorted(results):
                    print(f"  - {name}")

                # Register generated deliverables in session for tracking
                self._register_deliverables(milestone_number, results, out_dir)
        except Exception:
            logger.warning("Template population failed (non-critical)", exc_info=True)

    # ── Deliverable Registration ────────────────────────────────────

    _FILENAME_TO_CATEGORY = {
        "01_equipment_hierarchy.xlsx": "HIERARCHY",
        "02_criticality_assessment.xlsx": "CRITICALITY",
        "03_failure_modes.xlsx": "FMECA",
        "04_maintenance_tasks.xlsx": "TASKS",
        "05_work_packages.xlsx": "WORK_PACKAGES",
        "07_spare_parts_inventory.xlsx": "MATERIALS",
        "14_maintenance_strategy.xlsx": "RCM_DECISIONS",
    }

    _FILENAME_TO_MILESTONE = {
        "01_equipment_hierarchy.xlsx": 1,
        "02_criticality_assessment.xlsx": 1,
        "03_failure_modes.xlsx": 2,
        "04_maintenance_tasks.xlsx": 3,
        "05_work_packages.xlsx": 3,
        "07_spare_parts_inventory.xlsx": 3,
        "14_maintenance_strategy.xlsx": 3,
    }

    def _register_deliverables(
        self, milestone_number: int, results: dict, out_dir
    ) -> None:
        """Register generated template files as deliverable records in session.

        This populates session.deliverables so that _update_deliverable_status()
        and _link_quality_scores_to_deliverables() have records to operate on.
        """
        try:
            from datetime import datetime, timezone
            import uuid
            from tools.engines.deliverable_tracking_engine import DEFAULT_HOURS
            from tools.models.schemas import DeliverableCategory

            new_deliverables = []
            for filename, path in results.items():
                category = self._FILENAME_TO_CATEGORY.get(filename, "")
                d_milestone = self._FILENAME_TO_MILESTONE.get(filename, milestone_number)
                # Look up estimated hours from consulting benchmarks
                est_hours = 0.0
                try:
                    est_hours = DEFAULT_HOURS.get(DeliverableCategory(category), 4.0)
                except ValueError:
                    est_hours = 4.0
                new_deliverables.append({
                    "deliverable_id": str(uuid.uuid4()),
                    "name": filename.replace(".xlsx", "").replace("_", " ").title(),
                    "name_fr": filename,
                    "category": category,
                    "milestone": d_milestone,
                    "status": "SUBMITTED",
                    "estimated_hours": est_hours,
                    "artifact_paths": [str(path)],
                    "client_slug": self.session.client_slug or "",
                    "project_slug": self.session.project_slug or "",
                    "assigned_agent": "orchestrator",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                })

            if new_deliverables:
                self.session.write_entities(
                    "deliverables", new_deliverables, "orchestrator"
                )
                logger.info(
                    "Registered %d deliverables for milestone %d",
                    len(new_deliverables), milestone_number,
                )
        except Exception:
            logger.debug("Failed to register deliverables (non-critical)", exc_info=True)

    def _save_memory_learning(
        self, feedback: str, action: str, milestone: int, attempt: int
    ) -> None:
        """Extract and save learning from gate feedback to client memory."""
        if not self._memory_dir:
            return
        try:
            from agents._shared.memory import (
                MILESTONE_TO_STAGES,
                extract_learning,
                save_deviation,
                save_pattern,
            )

            learning = extract_learning(feedback, action)
            if not learning:
                return

            if learning["type"] == "deviation":
                save_deviation(
                    self._memory_dir,
                    f"M{milestone}-{attempt}",
                    learning["content"],
                )
            elif learning["type"] == "pattern":
                stages = MILESTONE_TO_STAGES.get(milestone, [])
                if stages:
                    save_pattern(self._memory_dir, stages[0], learning["content"])
        except Exception:
            logger.debug("Memory learning save failed (non-critical)", exc_info=True)

    def _update_execution_plan(self, milestone_number: int) -> None:
        """Mark execution plan items for this milestone as completed."""
        from pathlib import Path
        from agents.orchestration.execution_plan import ExecutionPlan, PlanStatus

        plan_path = self.session.execution_plan_path
        if not plan_path:
            # Try default location
            if self.session.client_slug and self.session.project_slug:
                from agents._shared.paths import get_state_dir
                default = get_state_dir(
                    self.session.client_slug, self.session.project_slug
                ) / "execution-plan.yaml"
                if default.is_file():
                    plan_path = str(default)

        if not plan_path or not Path(plan_path).is_file():
            return

        try:
            plan = ExecutionPlan.from_file(plan_path)
            for stage in plan.stages:
                if stage.milestone == milestone_number:
                    for item in stage.items:
                        if item.status != PlanStatus.COMPLETED:
                            item.mark_completed()
                    stage.recalculate_status()
            plan.to_file(plan_path)
            logger.info(
                "Execution plan updated: milestone %d items marked completed",
                milestone_number,
            )
        except Exception:
            logger.debug("Failed to update execution plan (non-critical)", exc_info=True)

    def _update_deliverable_status(self, milestone_number: int) -> None:
        """Transition DRAFT/IN_PROGRESS deliverables for this milestone to SUBMITTED.

        Called after a milestone is approved. Non-critical — logs and continues
        if the deliverable service or engine is unavailable.
        """
        try:
            from tools.engines.deliverable_tracking_engine import DeliverableTrackingEngine
            from tools.models.schemas import DeliverableStatus

            deliverables = self.session.deliverables
            updated = 0
            for d in deliverables:
                if d.get("milestone") != milestone_number:
                    continue
                current = d.get("status", "DRAFT")
                if current in ("DRAFT", "IN_PROGRESS"):
                    # Walk through valid transitions to reach SUBMITTED
                    try:
                        status = DeliverableStatus(current)
                        # DRAFT -> IN_PROGRESS -> SUBMITTED
                        if status == DeliverableStatus.DRAFT:
                            DeliverableTrackingEngine.transition(status, DeliverableStatus.IN_PROGRESS)
                            d["status"] = "IN_PROGRESS"
                            status = DeliverableStatus.IN_PROGRESS
                        if status == DeliverableStatus.IN_PROGRESS:
                            DeliverableTrackingEngine.transition(status, DeliverableStatus.SUBMITTED)
                            d["status"] = "SUBMITTED"
                            from datetime import datetime, timezone
                            d["submitted_at"] = datetime.now(timezone.utc).isoformat()
                            updated += 1
                    except (ValueError, KeyError):
                        pass

            if updated:
                logger.info(
                    "Deliverable status updated: %d deliverables for milestone %d → SUBMITTED",
                    updated,
                    milestone_number,
                )
        except Exception:
            logger.debug("Failed to update deliverable status (non-critical)", exc_info=True)

    def _auto_checkpoint(self) -> None:
        """Save an auto-checkpoint after each agent interaction."""
        from agents.orchestration.checkpoint import auto_checkpoint

        try:
            if self.checkpoint_dir:
                from pathlib import Path
                auto_checkpoint(self.session, Path(self.checkpoint_dir))
            elif self.session.client_slug and self.session.project_slug:
                auto_checkpoint(self.session)
        except Exception:
            logger.debug("Auto-checkpoint failed (non-critical)", exc_info=True)

    # ------------------------------------------------------------------
    # Direct specialist orchestration (replaces orchestrator.run() loop)
    # ------------------------------------------------------------------

    def _run_milestone_agents(self, gate: MilestoneGate) -> str:
        """Dispatch the appropriate specialist agents for each milestone.

        Returns the combined agent response text (used for audit trail).
        Entities are written to self.session as a side-effect.
        """
        context = (
            f"Equipment: {self.session.equipment_tag}\n"
            f"Plant: {self.session.plant_code}"
        )
        if gate.human_feedback:
            context += f"\nHuman feedback from previous attempt: {gate.human_feedback}"

        dispatch = {
            1: self._run_milestone_1,
            2: self._run_milestone_2,
            3: self._run_milestone_3,
            4: self._run_milestone_4,
        }
        fn = dispatch.get(gate.number)
        if fn is None:
            logger.warning("No agent dispatch for milestone %d", gate.number)
            return ""
        return fn(context)

    def _run_milestone_1(self, context: str) -> str:
        """M1: Reliability agent builds hierarchy and assesses criticality."""
        instruction = (
            f"{context}\n\n"
            "TASK — Milestone 1: Hierarchy Decomposition + Criticality Assessment\n\n"
            "You MUST follow these steps IN ORDER:\n\n"
            "Step 1 — Discover equipment type:\n"
            "  Call get_equipment_types (no args) to list available types from the library.\n"
            "  Find the matching type for the equipment (e.g. SAG_MILL for a SAG Mill).\n\n"
            "Step 2 — Build Equipment Hierarchy:\n"
            "  Call build_hierarchy_from_vendor with input_json containing:\n"
            f'    {{"plant_id": "{self.session.plant_code}", "area_code": "GRD", '
            '"equipment_type": "<type from step 1>", "manufacturer": "<if known>", "power_kw": <if known>}\n'
            "  This tool returns hierarchy_nodes (the full 6-level hierarchy) — save these for your response.\n\n"
            "Step 3 — Assess Criticality for each Maintainable Item:\n"
            "  For each maintainable item node_id from step 2, call assess_criticality with input_json:\n"
            '    {"assessment_id": "CA-<seq>", "node_id": "<mi_node_id from step 2>", '
            '"assessed_by": "reliability_agent", "assessed_at": "2026-01-01T00:00:00", '
            '"criteria_scores": [{"category": "SAFETY", "score": <1-5>}, {"category": "HEALTH", "score": <1-5>}, '
            '{"category": "ENVIRONMENT", "score": <1-5>}, {"category": "PRODUCTION", "score": <1-5>}, '
            '{"category": "OPERATING_COST", "score": <1-5>}, {"category": "CAPITAL_COST", "score": <1-5>}, '
            '{"category": "SCHEDULE", "score": <1-5>}, {"category": "REVENUE", "score": <1-5>}, '
            '{"category": "COMMUNICATIONS", "score": <1-5>}, {"category": "COMPLIANCE", "score": <1-5>}, '
            '{"category": "REPUTATION", "score": <1-5>}], "probability": <1-5>}\n\n'
            "Step 4 — Return results:\n"
            "  Your FINAL response MUST contain a ```json fenced code block with ALL data.\n"
            "  Include the hierarchy_nodes array from step 2 AND criticality_assessments from step 3.\n"
            "  Each criticality assessment in the output must have: assessment_id, node_id, risk_class, "
            "overall_score, assessed_at, assessed_by.\n\n"
            "```json\n"
            '{"hierarchy_nodes": [<nodes from build_hierarchy_from_vendor>], '
            '"criticality_assessments": [<results from assess_criticality calls>]}\n'
            "```\n"
        )
        response = self.orchestrator.delegate("reliability", instruction)
        m1_keys = ["hierarchy_nodes", "criticality_assessments"]
        entities = _extract_entities_from_response(response)

        if not entities.get("hierarchy_nodes"):
            logger.info("M1: text extraction missed entities — scanning tool results")
            agent = self.orchestrator.reliability
            logger.info("M1: agent history has %d turns", len(agent.history))
            for i, turn in enumerate(agent.history):
                tr_list = getattr(turn, "tool_results", [])
                tc_list = getattr(turn, "tool_calls", [])
                logger.info("M1: turn %d: %d tool_calls, %d tool_results",
                            i, len(tc_list), len(tr_list))
                for tc in tc_list:
                    logger.info("M1:   tool_call: %s", tc.get("name", "?"))
                for tr in tr_list:
                    result_str = tr.get("result", "")
                    logger.info("M1:   tool_result for %s: len=%d, preview=%.200s",
                                tr.get("tool_name", "?"), len(result_str), result_str)
            tool_entities = _extract_entities_from_tool_results(agent, m1_keys)
            for k in m1_keys:
                if k not in entities and k in tool_entities:
                    entities[k] = tool_entities[k]

        if not entities:
            logger.warning("M1: no entities extracted from response or tool results (len=%d)", len(response))

        # Post-extraction sanitization: ensure assessments aren't mixed into nodes
        entities = _sanitize_entities(entities, m1_keys)

        if nodes := entities.get("hierarchy_nodes"):
            # Ensure L1-L3 ancestor nodes exist (build_from_vendor only creates L4+)
            nodes = _ensure_ancestor_nodes(
                nodes, self.session.plant_code, self.session.equipment_tag,
            )
            try:
                self.session.write_entities("hierarchy_nodes", nodes, "reliability")
                logger.info("M1: wrote %d hierarchy_nodes", len(nodes))
            except Exception:
                logger.warning("Failed to write hierarchy_nodes", exc_info=True)
        if assessments := entities.get("criticality_assessments"):
            try:
                self.session.write_entities("criticality_assessments", assessments, "reliability")
                logger.info("M1: wrote %d criticality_assessments", len(assessments))
            except Exception:
                logger.warning("Failed to write criticality_assessments", exc_info=True)

        return response

    def _run_milestone_2(self, context: str) -> str:
        """M2: Reliability agent performs FMECA + RCM decision tree."""
        counts = self.session.get_entity_counts()
        instruction = (
            f"{context}\n"
            f"Existing: {counts.get('hierarchy_nodes', 0)} hierarchy nodes, "
            f"{counts.get('criticality_assessments', 0)} criticality assessments\n\n"
            "TASK — Milestone 2: FMECA Completion + RCM Decisions\n\n"
            "Step 1 — Functions & Functional Failures:\n"
            "  For each Maintainable Item, define operating functions and functional failures.\n"
            "  Each Function MUST include: function_id (str), node_id (str, matches a hierarchy node), "
            "function_type (str: PRIMARY or SECONDARY), description (str), description_fr (str, French)\n"
            "  Each FunctionalFailure MUST include: failure_id (str), function_id (str), "
            "failure_type (str: TOTAL or PARTIAL), description (str), description_fr (str, French)\n\n"
            "Step 2 — Failure Modes (72-combo MANDATORY):\n"
            "  Use validate_fm_combination tool to verify each Mechanism+Cause combination.\n"
            "  Only use combinations from the 72-combo MASTER table.\n"
            "  Each FailureMode MUST include: failure_mode_id (str, e.g. FM-001), "
            "functional_failure_id (str, references a FunctionalFailure), "
            "what (str, describes the failure mode starting with capital letter), "
            "mechanism (str), cause (str), node_id (str, the MI it belongs to)\n\n"
            "Step 3 — RCM Decision Tree:\n"
            "  Use rcm_decide tool for each failure mode to determine the maintenance strategy.\n"
            "  Required rcm_decide input: is_hidden (bool), failure_consequence (str: HIDDEN_SAFETY, "
            "HIDDEN_NONSAFETY, EVIDENT_SAFETY, EVIDENT_ENVIRONMENTAL, EVIDENT_OPERATIONAL, "
            "EVIDENT_NONOPERATIONAL), cbm_technically_feasible (bool), cbm_economically_viable (bool), "
            "ft_feasible (bool).\n"
            "  After rcm_decide, add to each failure mode: strategy_type (from result), "
            "failure_consequence (from input), is_hidden (from input)\n\n"
            "CRITICAL: Your final response MUST contain a ```json fenced code block with the result object.\n"
            "Do NOT put any text inside the JSON block — only the JSON object.\n"
            "ALL three arrays MUST be populated (not empty).\n\n"
            "```json\n"
            '{"functions": [{function_id, node_id, function_type, description, description_fr}], '
            '"functional_failures": [{failure_id, function_id, failure_type, description, description_fr}], '
            '"failure_modes": [{failure_mode_id, functional_failure_id, what, mechanism, cause, '
            "node_id, strategy_type, failure_consequence, is_hidden}]}\n"
            "```\n"
        )
        response = self.orchestrator.delegate("reliability", instruction)
        m2_keys = ["functions", "functional_failures", "failure_modes"]
        entities = _extract_entities_from_response(response)

        if not any(entities.get(k) for k in m2_keys):
            logger.info("M2: text extraction missed entities — scanning tool results")
            tool_entities = _extract_entities_from_tool_results(
                self.orchestrator.reliability, m2_keys,
            )
            for k in m2_keys:
                if k not in entities and k in tool_entities:
                    entities[k] = tool_entities[k]

        if not entities:
            logger.warning("M2: no entities extracted from response or tool results (len=%d)", len(response))

        # Post-extraction sanitization: ensure failures aren't mixed into functions
        entities = _sanitize_entities(entities, m2_keys)

        # Enrich: synthesise missing functions/functional_failures, fill FM fields
        entities = _enrich_m2_entities(
            entities,
            hierarchy_nodes=self.session.hierarchy_nodes,
            agent=self.orchestrator.reliability,
        )

        for entity_type in m2_keys:
            if items := entities.get(entity_type):
                try:
                    self.session.write_entities(entity_type, items, "reliability")
                    logger.info("M2: wrote %d %s", len(items), entity_type)
                except Exception:
                    logger.warning("Failed to write %s", entity_type, exc_info=True)

        return response

    def _run_milestone_3(self, context: str) -> str:
        """M3: Planning creates tasks + WPs; Spare Parts assigns materials."""
        counts = self.session.get_entity_counts()
        # Planning: tasks + work packages
        planning_instruction = (
            f"{context}\n"
            f"Existing: {counts.get('failure_modes', 0)} failure modes with RCM decisions\n\n"
            "TASK — Milestone 3 (Planning): Maintenance Tasks + Work Packages\n\n"
            "Step 1 — Maintenance Tasks:\n"
            "  Create maintenance tasks for each RCM decision. Max 72 chars per task name.\n"
            "  Each task MUST include: task_id (str), task_type (str: INSPECT, REPLACE, REPAIR, OVERHAUL, LUBRICATE, CALIBRATE, TEST), "
            "description (str, max 72 chars), failure_mode_id (str), frequency_days (int), "
            "estimated_hours (float), material_required (bool — MUST be true for REPLACE tasks per T-16 rule)\n\n"
            "Step 2 — Work Packages:\n"
            "  Use assemble_work_package tool to group related tasks into work packages.\n"
            "  Each WP MUST include: wp_id (str), name (str), task_ids (list of str), "
            "craft (str), estimated_hours (float)\n\n"
            "CRITICAL: Your final response MUST contain a ```json fenced code block with the result object.\n"
            "Do NOT put any text inside the JSON block — only the JSON object.\n\n"
            "```json\n"
            '{"maintenance_tasks": [...], "work_packages": [...]}\n'
            "```\n"
        )
        planning_response = self.orchestrator.delegate("planning", planning_instruction)
        m3_keys = ["maintenance_tasks", "work_packages"]
        plan_entities = _extract_entities_from_response(planning_response)

        if not any(plan_entities.get(k) for k in m3_keys):
            logger.info("M3: text extraction missed entities — scanning tool results")
            tool_entities = _extract_entities_from_tool_results(
                self.orchestrator.planning, m3_keys,
            )
            for k in m3_keys:
                if k not in plan_entities and k in tool_entities:
                    plan_entities[k] = tool_entities[k]

        if not plan_entities:
            logger.warning("M3: no entities extracted from response or tool results (len=%d)", len(planning_response))

        # Post-extraction sanitization: ensure WPs aren't mixed into tasks
        plan_entities = _sanitize_entities(plan_entities, m3_keys)

        # Enrich: ensure task IDs, T-16 rule, description length
        plan_entities = _enrich_m3_entities(plan_entities, self.session.failure_modes)

        for entity_type in m3_keys:
            if items := plan_entities.get(entity_type):
                try:
                    self.session.write_entities(entity_type, items, "planning")
                    logger.info("M3: wrote %d %s", len(items), entity_type)
                except Exception:
                    logger.warning("Failed to write %s", entity_type, exc_info=True)

        # Spare Parts: materials for REPLACE tasks — check multiple possible key names
        replace_tasks = [
            t for t in self.session.maintenance_tasks
            if (t.get("task_type") or t.get("type") or "").upper() == "REPLACE"
            or t.get("material_required", False)
        ]
        if replace_tasks:
            sp_instruction = (
                f"{context}\n"
                f"Tasks requiring materials (T-16 rule): {json.dumps(replace_tasks[:10], default=str)}\n\n"
                "TASK — Assign materials to REPLACE tasks:\n"
                "  Use suggest_materials or lookup_bom tools to assign parts.\n"
                "  Each assignment MUST include: task_id (str), material_number (str), description (str), quantity (int), unit (str)\n\n"
                "CRITICAL: Your final response MUST contain a ```json fenced code block:\n\n"
                "```json\n"
                '{"material_assignments": [...]}\n'
                "```\n"
            )
            sp_response = self.orchestrator.delegate("spare_parts", sp_instruction)
            sp_entities = _extract_entities_from_response(sp_response)
            if materials := sp_entities.get("material_assignments"):
                try:
                    self.session.write_entities("material_assignments", materials, "spare_parts")
                    logger.info("M3: wrote %d material_assignments", len(materials))
                except Exception:
                    logger.warning("Failed to write material_assignments", exc_info=True)

        return planning_response

    def _run_milestone_4(self, context: str) -> str:
        """M4: Planning generates SAP upload package."""
        counts = self.session.get_entity_counts()
        instruction = (
            f"{context}\n"
            f"Existing: {counts.get('work_packages', 0)} work packages, "
            f"{counts.get('maintenance_tasks', 0)} tasks\n\n"
            "TASK — Milestone 4: SAP PM Upload Package\n\n"
            "Use generate_sap_export or assemble_sap_package tools to create:\n"
            "  1. Functional Locations (max 40 chars each)\n"
            "  2. Task Lists with Operations (short text max 72 chars)\n"
            "  3. Maintenance Plans with scheduling parameters\n\n"
            "REMINDER: All outputs are DRAFT. Never auto-submit to SAP.\n\n"
            "The sap_upload_package MUST include:\n"
            '  - plant_code: str (e.g. "OCP-JFC")\n'
            '  - status: "DRAFT"\n'
            '  - maintenance_plan: {plan_id, description, cycle_unit, cycle_value}\n'
            '  - maintenance_items: [{item_id, functional_location, description, ...}]\n'
            '  - task_lists: [{task_list_id, description, operations: [{...}]}]\n\n'
            "CRITICAL: Your final response MUST contain a ```json fenced code block:\n\n"
            "```json\n"
            '{"sap_upload_package": {...}}\n'
            "```\n"
        )
        response = self.orchestrator.delegate("planning", instruction)
        entities = _extract_entities_from_response(response)

        if not entities:
            logger.warning("M4: entity extraction returned empty dict from response (len=%d)", len(response))

        if pkg := entities.get("sap_upload_package"):
            self.session.sap_upload_package = pkg
            logger.info("M4: SAP upload package generated")

        return response

    def _build_milestone_instruction(self, gate: MilestoneGate) -> str:
        """Build a concise audit-trail label for each milestone."""
        counts = self.session.get_entity_counts()
        return (
            f"M{gate.number} — Equipment: {self.session.equipment_tag} "
            f"| Plant: {self.session.plant_code} "
            f"| Nodes: {counts.get('hierarchy_nodes', 0)} "
            f"| FMs: {counts.get('failure_modes', 0)} "
            f"| Tasks: {counts.get('maintenance_tasks', 0)}"
        )
