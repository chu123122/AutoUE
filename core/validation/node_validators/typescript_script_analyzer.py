"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import WorkflowValidationError, require_list, require_string, validate_json_path, validate_ts_path

def validate_typescript_script_analyzer(node: str, data: dict[str, Any]) -> None:
    for key in ("typescript_sources", "implementation_slots", "missing_slots"):
        require_list(node, data, key)
    for si, source in enumerate(data.get("typescript_sources", [])):
        if not isinstance(source, dict):
            raise WorkflowValidationError(f"{node}: typescript_sources[{si}] must be object")
        validate_ts_path(node, require_string(node, source, "path", non_empty=True), label=f"typescript_sources[{si}].path")
    targets = {}
    for si, slot in enumerate(data.get("implementation_slots", [])):
        if not isinstance(slot, dict):
            raise WorkflowValidationError(f"{node}: implementation_slots[{si}] must be object")
        behavior_id = require_string(node, slot, "behavior_id", non_empty=True)
        require_string(node, slot, "entity_id", non_empty=True)
        require_string(node, slot, "flow_id", non_empty=True)
        validate_json_path(node, require_string(node, slot, "runtime_mapping_path", non_empty=True), label=f"implementation_slots[{si}].runtime_mapping_path")
        target = require_string(node, slot, "target_ts_file", non_empty=True)
        validate_ts_path(node, target, label=f"implementation_slots[{si}].target_ts_file")
        previous = targets.get(target)
        if previous and previous != behavior_id:
            raise WorkflowValidationError(f"{node}: one workflow template target file must not collapse multiple behaviors: {target} used by {previous} and {behavior_id}")
        targets[target] = behavior_id
