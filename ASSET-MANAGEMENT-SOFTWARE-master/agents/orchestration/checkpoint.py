"""Session checkpoint management for crash recovery.

Supports two modes:
1. Milestone checkpoints: saved after each milestone approval (named by milestone).
2. Auto-checkpoints: saved after each agent interaction (timestamped, with purge).

Enables workflow resumption from the last approved milestone or the latest
auto-checkpoint in case of mid-milestone crashes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from agents.orchestration.session_state import SessionState

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_DIR = Path("sessions/checkpoints")
DEFAULT_MAX_AUTO_CHECKPOINTS = 10


def _resolve_checkpoint_dir(
    session: SessionState, checkpoint_dir: Path | None = None
) -> Path:
    """Resolve checkpoint directory, preferring client project path if available."""
    if checkpoint_dir is not None:
        return checkpoint_dir
    if session.client_slug and session.project_slug:
        from agents._shared.paths import get_checkpoint_dir
        return get_checkpoint_dir(session.client_slug, session.project_slug)
    return DEFAULT_CHECKPOINT_DIR


# ---------------------------------------------------------------------------
# Milestone checkpoints (on approve)
# ---------------------------------------------------------------------------

def save_checkpoint(
    session: SessionState,
    milestone_number: int,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
) -> Path:
    """Save session state after milestone approval.

    Returns the path to the written checkpoint file.
    """
    checkpoint_dir = _resolve_checkpoint_dir(session, checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / f"{session.session_id}_m{milestone_number}.json"
    path.write_text(session.to_json(), encoding="utf-8")
    return path


def load_checkpoint(
    session_id: str,
    milestone_number: int,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
) -> SessionState | None:
    """Load a checkpoint. Returns None if not found."""
    path = checkpoint_dir / f"{session_id}_m{milestone_number}.json"
    if not path.exists():
        return None
    return SessionState.from_json(path.read_text(encoding="utf-8"))


def find_latest_checkpoint(
    session_id: str,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
) -> tuple[int, SessionState] | None:
    """Find the most recent checkpoint (highest milestone).

    Returns (milestone_num, session) or None if no checkpoints exist.
    """
    for m in range(4, 0, -1):
        session = load_checkpoint(session_id, m, checkpoint_dir)
        if session is not None:
            return (m, session)
    return None


# ---------------------------------------------------------------------------
# Auto-checkpoints (after each agent interaction)
# ---------------------------------------------------------------------------

def auto_checkpoint(
    session: SessionState,
    checkpoint_dir: Path | None = None,
    max_checkpoints: int = DEFAULT_MAX_AUTO_CHECKPOINTS,
) -> Path:
    """Save a timestamped auto-checkpoint after an agent interaction.

    Auto-checkpoints use the naming pattern:
        {session_id}_auto_{ISO-timestamp}.json

    Old auto-checkpoints beyond max_checkpoints are purged.

    Returns the path to the written checkpoint file.
    """
    resolved_dir = _resolve_checkpoint_dir(session, checkpoint_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
    path = resolved_dir / f"{session.session_id}_auto_{timestamp}.json"
    path.write_text(session.to_json(), encoding="utf-8")

    # Purge old auto-checkpoints beyond the limit
    _purge_old_auto_checkpoints(session.session_id, resolved_dir, max_checkpoints)

    logger.debug("Auto-checkpoint saved: %s", path.name)
    return path


def _purge_old_auto_checkpoints(
    session_id: str,
    checkpoint_dir: Path,
    max_checkpoints: int,
) -> int:
    """Remove oldest auto-checkpoints if count exceeds max_checkpoints.

    Returns the number of files removed.
    """
    pattern = f"{session_id}_auto_*.json"
    auto_files = sorted(checkpoint_dir.glob(pattern))

    if len(auto_files) <= max_checkpoints:
        return 0

    to_remove = auto_files[: len(auto_files) - max_checkpoints]
    for f in to_remove:
        f.unlink()
        logger.debug("Purged old auto-checkpoint: %s", f.name)

    return len(to_remove)


def recover_from_checkpoint(
    session_id: str,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
) -> tuple[str, SessionState] | None:
    """Recover from the latest checkpoint (milestone or auto).

    Checks milestone checkpoints first (most stable), then falls back
    to auto-checkpoints.

    Returns ("m{N}", session) or ("auto_{timestamp}", session) or None.
    """
    # Try milestone checkpoints first
    milestone_result = find_latest_checkpoint(session_id, checkpoint_dir)
    if milestone_result is not None:
        m_num, session = milestone_result
        return (f"m{m_num}", session)

    # Fall back to auto-checkpoints
    pattern = f"{session_id}_auto_*.json"
    auto_files = sorted(checkpoint_dir.glob(pattern))
    if auto_files:
        latest = auto_files[-1]
        session = SessionState.from_json(latest.read_text(encoding="utf-8"))
        # Extract the label from filename
        label = latest.stem.replace(f"{session_id}_", "")
        return (label, session)

    return None
