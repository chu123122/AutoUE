"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import require_string

def validate_scene_and_gameplay_splitter(node: str, data: dict[str, Any]) -> None:
    require_string(node, data, "scene_description", non_empty=True)
    require_string(node, data, "gameplay_description", non_empty=True)
