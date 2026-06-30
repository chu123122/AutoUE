"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import WorkflowValidationError, require_list, require_string, validate_json_path, validate_ts_path

def _eval_trace(node: str, trace: Any, label: str) -> dict[str, Any]:
    if not isinstance(trace, dict):
        raise WorkflowValidationError(f"{node}: {label} must be object")
    for key in ("entity_id", "ability_id", "behavior_id", "flow_id"):
        require_string(node, trace, key, non_empty=True)
    validate_json_path(node, require_string(node, trace, "runtime_mapping_path", non_empty=True), label=f"{label}.runtime_mapping_path")
    for key in ("engine_port_ids", "adjudication_paths", "ts_files"):
        require_list(node, trace, key, non_empty=True)
    for pi, path in enumerate(trace["adjudication_paths"]):
        if not isinstance(path, str):
            raise WorkflowValidationError(f"{node}: {label}.adjudication_paths[{pi}] must be string")
        validate_json_path(node, path, label=f"{label}.adjudication_paths[{pi}]")
    for pi, path in enumerate(trace["ts_files"]):
        if not isinstance(path, str):
            raise WorkflowValidationError(f"{node}: {label}.ts_files[{pi}] must be string")
        validate_ts_path(node, path, label=f"{label}.ts_files[{pi}]")
    for pi, port in enumerate(trace["engine_port_ids"]):
        if not isinstance(port, str) or not port.strip():
            raise WorkflowValidationError(f"{node}: {label}.engine_port_ids[{pi}] must be non-empty string")
    return trace

def validate_evaluate_instruction_generator(node: str, data: dict[str, Any]) -> None:
    for ii, instruction in enumerate(require_list(node, data, "evaluation_instructions", non_empty=True)):
        if not isinstance(instruction, dict):
            raise WorkflowValidationError(f"{node}: evaluation_instructions[{ii}] must be object")
        if not isinstance(instruction.get("step_id"), int):
            raise WorkflowValidationError(f"{node}: evaluation_instructions[{ii}].step_id must be integer")
        for key in ("action", "target", "description", "driver", "executor_action"):
            require_string(node, instruction, key, non_empty=True)
        require_list(node, instruction, "expected", non_empty=True)
        _eval_trace(node, instruction.get("trace"), f"evaluation_instructions[{ii}].trace")
    for ci, coverage in enumerate(require_list(node, data, "coverage", non_empty=True)):
        _eval_trace(node, coverage, f"coverage[{ci}]")
