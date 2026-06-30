"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import ALLOWED_STAGES, WorkflowValidationError, require_list, require_string

def validate_thin_gameplay_flow_planner(node: str, data: dict[str, Any]) -> None:
    for fi, flow in enumerate(require_list(node, data, "flows", non_empty=True)):
        if not isinstance(flow, dict):
            raise WorkflowValidationError(f"{node}: flows[{fi}] must be object")
        for key in ("flow_id", "source_behavior_id", "entity_id", "ability_id"):
            require_string(node, flow, key, non_empty=True)
        ports = set()
        for si, stage in enumerate(require_list(node, flow, "stages", non_empty=True)):
            if not isinstance(stage, dict):
                raise WorkflowValidationError(f"{node}: flows[{fi}].stages[{si}] must be object")
            stage_name = require_string(node, stage, "stage", non_empty=True)
            if stage_name not in ALLOWED_STAGES:
                raise WorkflowValidationError(f"{node}: unknown flow stage: {stage_name}")
            require_string(node, stage, "contract", non_empty=True)
            if "inputs" in stage:
                require_list(node, stage, "inputs")
            if "outputs" in stage:
                require_list(node, stage, "outputs")
            for port in require_list(node, stage, "engine_ports"):
                if not isinstance(port, str) or not port.strip():
                    raise WorkflowValidationError(f"{node}: engine_ports must contain non-empty strings")
                ports.add(port)
        if not ports:
            raise WorkflowValidationError(f"{node}: every flow must declare at least one engine_port")
        if "verification" in flow:
            require_list(node, flow, "verification")
