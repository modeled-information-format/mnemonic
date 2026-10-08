"""Decay strength calculation and frontmatter updates."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .memory_file import MemoryFile
from .report import Report

# ISO 8601 duration: P[n]D or P[n]Y[n]M[n]D
DURATION_PATTERN = re.compile(r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?")


def parse_duration_days(duration_str: str) -> Optional[int]:
    """Parse ISO 8601 duration string to total days.

    Supports P30D, P1Y, P6M, P1Y6M15D etc.
    """
    if not duration_str:
        return None
    match = DURATION_PATTERN.match(duration_str.strip())
    if not match:
        return None
    years = int(match.group(1) or 0)
    months = int(match.group(2) or 0)
    days_val = int(match.group(3) or 0)
    return years * 365 + months * 30 + days_val


def calculate_strength(
    days_since_access: float,
    half_life_days: float,
    current_strength: float = 1.0,
    model: str = "exponential",
) -> float:
    """Calculate new decay strength.

    Models:
        exponential: strength * 0.5^(days / half_life)
        linear: strength * max(0, 1 - days / half_life)
        step: 1.0 if days < half_life else 0.0
        none: current_strength (no decay)
    """
    if model == "none" or half_life_days <= 0:
        return current_strength
    if model == "linear":
        return max(0.0, current_strength * (1.0 - days_since_access / half_life_days))
    if model == "step":
        return current_strength if days_since_access < half_life_days else 0.0
    # Default: exponential
    decay_factor = 0.5 ** (days_since_access / half_life_days)
    return current_strength * decay_factor


def _parse_iso_datetime(s: str) -> Optional[datetime]:
    """Parse ISO 8601 datetime, handling Z suffix."""
    if not s:
        return None
    s = str(s).strip().strip('"').strip("'")
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def update_decay(roots: List[Path], report: Report, dry_run: bool = False) -> int:
    """Recalculate and update decay strength for all memories.

    Returns number of memories updated.
    """
    now = datetime.now(timezone.utc)
    updated = 0

    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.memory.md")):
            mem = MemoryFile(path)

            # Get decay parameters
            model = mem.get_nested("temporal", "decay", "model", default="none")
            if model == "none":
                continue

            # halfLife (MIF 1.4.1), falling back to legacy half_life
            half_life_str = mem.get_compat("temporal", "decay", "halfLife", default="")
            if not half_life_str:
                report.warning(
                    "decay",
                    f"Decay model '{model}' but no halfLife specified",
                    file_path=path,
                )
                continue

            half_life_days = parse_duration_days(str(half_life_str))
            if half_life_days is None or half_life_days <= 0:
                report.warning(
                    "decay",
                    f"Invalid halfLife duration: {half_life_str}",
                    file_path=path,
                )
                continue

            # Get current strength
            current_str = mem.get_nested("temporal", "decay", "currentStrength", default=None)
            if current_str is None:
                current_str = mem.get_nested("temporal", "decay", "strength", default=None)
            current_strength = float(current_str) if current_str is not None else 1.0

            # Get last access time
            # lastAccessed (MIF 1.4.1), falling back to legacy last_accessed
            last_accessed_str = mem.get_compat("temporal", "lastAccessed", default=None)
            if last_accessed_str is None:
                # Fall back to created date
                last_accessed_str = mem.get("created", "")

            last_accessed = _parse_iso_datetime(str(last_accessed_str))
            if last_accessed is None:
                report.warning(
                    "decay",
                    "Cannot determine last access time",
                    file_path=path,
                )
                continue

            days_since = (now - last_accessed).total_seconds() / 86400.0
            # Strength is a function of time since last access, so compute it
            # from full strength rather than from the stored, already-decayed
            # value: re-applying the whole interval on every run compounded the
            # decay. min() keeps a strength someone deliberately set lower, and
            # makes repeated runs idempotent.
            new_strength = min(
                current_strength,
                calculate_strength(days_since, half_life_days, 1.0, str(model)),
            )
            new_strength = round(new_strength, 4)

            if abs(new_strength - current_strength) < 0.005:
                continue

            report.info(
                "decay",
                f"Strength: {current_strength:.2f} -> {new_strength:.4f}",
                file_path=path,
                fixed=not dry_run,
            )

            if not dry_run:
                # Update the strength field
                strength_key = (
                    "currentStrength"
                    if mem.get_nested("temporal", "decay", "currentStrength") is not None
                    else "strength"
                )
                mem.update_nested_field(["temporal", "decay", strength_key], str(new_strength))
                mem.save()
                updated += 1

    return updated
