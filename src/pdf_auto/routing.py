"""Pure routing decisions for Bluesky run documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def plan_names(message: Mapping[str, Any]) -> tuple[str, ...]:
    """Return normalized plan names from beamline start metadata.

    The beamline may encode ``sp_plan_name`` either as one string or as a
    sequence containing one or more strings.
    """
    value = message.get("sp_plan_name")
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def is_dark_start(message: Mapping[str, Any]) -> bool:
    """Return whether any configured plan name identifies a dark scan."""
    return any("dark" in name for name in plan_names(message))


def should_process_start(message: Mapping[str, Any]) -> bool:
    """Return whether a Bluesky start document should enter the workflow.

    Dark scans, runs already produced by an analysis workflow, and documents
    without ``sp_plan_name`` are excluded, matching the original consumer.
    """
    names = plan_names(message)
    if not names:
        return False
    if is_dark_start(message):
        return False
    return "original_run_uid" not in message
