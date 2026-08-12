"""Pure routing decisions for Bluesky run documents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def should_process_start(message: Mapping[str, Any]) -> bool:
    """Return whether a Bluesky start document should enter the workflow.

    Dark scans, runs already produced by an analysis workflow, and documents
    without ``sp_plan_name`` are excluded, matching the original consumer.
    """
    plan_name = message.get("sp_plan_name")
    if not isinstance(plan_name, str):
        return False
    if "dark" in plan_name:
        return False
    return "original_run_uid" not in message
