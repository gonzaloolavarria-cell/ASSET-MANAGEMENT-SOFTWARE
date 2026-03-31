"""Non-interactive live run — auto-approves milestone gates.

Usage:
    python -m scripts.live_run "SAG Mill 001" --plant OCP-JFC --output session.json
    python -m scripts.live_run "SAG Mill 001" --plant OCP-JFC --milestone 1 --output m1_only.json
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

# Force UTF-8 on Windows to avoid cp1252 encoding errors
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import logging

from dotenv import load_dotenv
load_dotenv()

# Enable INFO logging so we can see entity extraction progress
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s %(levelname)s: %(message)s",
)

from agents.orchestration.workflow import StrategyWorkflow


def auto_approve(milestone_number: int, summary: str) -> tuple[str, str]:
    """Auto-approve gate for unattended runs."""
    print("\n" + "=" * 60)
    print(summary)
    print("=" * 60)
    print(f"\n[AUTO-APPROVE] Milestone {milestone_number} -> approve")
    return ("approve", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="AMS Live Run (auto-approve)")
    parser.add_argument("equipment", help="Equipment description")
    parser.add_argument("--plant", default="OCP", help="SAP plant code")
    parser.add_argument("--output", "-o", help="Save session state to JSON file")
    parser.add_argument(
        "--milestone", "-m", type=int, default=4, choices=[1, 2, 3, 4],
        help="Stop after this milestone (default: 4 = all)",
    )
    args = parser.parse_args()

    stop_after = args.milestone

    def auto_approve_with_stop(milestone_number: int, summary: str) -> tuple[str, str]:
        """Auto-approve, then signal stop after target milestone."""
        print("\n" + "=" * 60)
        print(summary)
        print("=" * 60)
        print(f"\n[AUTO-APPROVE] Milestone {milestone_number} -> approve")
        if milestone_number >= stop_after:
            # Approve this milestone, then raise to break out of the loop
            raise _StopAfterMilestone(milestone_number)
        return ("approve", "")

    print(f"=== AMS Live Run (auto-approve, stop after M{stop_after}) ===")
    print(f"Equipment: {args.equipment}")
    print(f"Plant: {args.plant}\n")

    workflow = StrategyWorkflow(human_approval_fn=auto_approve_with_stop)

    try:
        session = workflow.run(args.equipment, plant_code=args.plant)
    except _StopAfterMilestone as e:
        print(f"\n[STOP] Reached target milestone M{e.milestone} — stopping.")
        # The approval callback raised BEFORE returning, so we need to
        # manually approve the gate that was being presented
        for gate in workflow.milestones:
            if gate.number == e.milestone and not gate.is_complete:
                gate.approve("")
                workflow._write_template_deliverables(gate.number)
                if gate.number == 4:
                    workflow._write_sap_xlsx()
        session = workflow.session
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user.")
        session = workflow.session
    except Exception as e:
        print(f"\n\nERROR: {e}")
        traceback.print_exc()
        session = workflow.session

    # Final summary
    print("\n" + "=" * 60)
    print("SESSION COMPLETE")
    print("=" * 60)
    counts = session.get_entity_counts()
    for entity, count in counts.items():
        if isinstance(count, bool):
            print(f"  {entity}: {'Yes' if count else 'No'}")
        elif count > 0:
            print(f"  {entity}: {count}")

    milestones_approved = sum(1 for m in workflow.milestones if m.is_complete)
    print(f"\nMilestones approved: {milestones_approved}/4")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(session.to_json())
        print(f"Session saved to: {args.output}")


class _StopAfterMilestone(Exception):
    """Internal signal to stop after a specific milestone."""
    def __init__(self, milestone: int):
        self.milestone = milestone
        super().__init__(f"Stop after milestone {milestone}")


if __name__ == "__main__":
    main()
