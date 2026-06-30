"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import ALLOWED_HIT_TYPES, ALLOWED_VERDICTS, WorkflowValidationError, require_dict, require_list, require_string, validate_json_path

def validate_ue_api_mcp_feasibility_searcher(node: str, data: dict[str, Any]) -> None:
    for qi, query in enumerate(require_list(node, data, "queries", non_empty=True)):
        if not isinstance(query, dict):
            raise WorkflowValidationError(f"{node}: queries[{qi}] must be object")
        for key in ("engine_port_id", "query", "notes"):
            require_string(node, query, key, non_empty=True)
        validate_json_path(node, require_string(node, query, "raw_path", non_empty=True), label=f"queries[{qi}].raw_path")
        validate_json_path(node, require_string(node, query, "adjudication_path", non_empty=True), label=f"queries[{qi}].adjudication_path")
        verdict = require_string(node, query, "verdict", non_empty=True)
        hit_type = require_string(node, query, "hit_type", non_empty=True)
        if verdict not in ALLOWED_VERDICTS:
            raise WorkflowValidationError(f"{node}: invalid verdict: {verdict}")
        if hit_type not in ALLOWED_HIT_TYPES:
            raise WorkflowValidationError(f"{node}: invalid hit_type: {hit_type}")
        if verdict == "hit" and hit_type == "none":
            raise WorkflowValidationError(f"{node}: hit verdict must use direct_hit or indirect_hit")
        if verdict == "miss" and hit_type != "none":
            raise WorkflowValidationError(f"{node}: miss verdict must use hit_type=none")
        require_list(node, query, "flow_ids", non_empty=True)
        require_list(node, query, "behavior_ids", non_empty=True)
        require_list(node, query, "evidence_symbols")
    require_dict(node, data, "summary")
