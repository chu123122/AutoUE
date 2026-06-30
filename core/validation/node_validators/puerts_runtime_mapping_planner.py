"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import ALLOWED_CARRIERS, ALLOWED_VERDICTS, WorkflowValidationError, require_dict, require_list, require_string, validate_json_path, validate_ts_path

def validate_puerts_runtime_mapping_planner(node: str, data: dict[str, Any]) -> None:
    runtime_mapping_path = require_string(node, data, "runtime_mapping_path", non_empty=True)
    validate_json_path(node, runtime_mapping_path, label="runtime_mapping_path")
    runtime_features = require_list(node, data, "runtime_features", non_empty=True)
    if any(not isinstance(item, str) or not item.strip() for item in runtime_features):
        raise WorkflowValidationError(f"{node}: runtime_features must contain non-empty strings")
    if any(item in {"status", "interaction"} for item in runtime_features):
        raise WorkflowValidationError(f"{node}: runtime_features must not contain status/interaction")
    validate_json_path(node, require_string(node, data, "behavior_spec_path", non_empty=True), label="behavior_spec_path")
    validate_json_path(node, require_string(node, data, "support_check_path", non_empty=True), label="support_check_path")
    behavior_spec = require_dict(node, data, "behavior_spec")
    if behavior_spec.get("schema_version") != "autoue-behavior-spec/v1":
        raise WorkflowValidationError(f"{node}: behavior_spec schema_version must be autoue-behavior-spec/v1")
    support_check = require_dict(node, data, "support_check")
    if support_check.get("status") != "supported":
        reasons = [item.get("reason", "") for item in support_check.get("unsupported_capabilities", []) if isinstance(item, dict)]
        raise WorkflowValidationError(f"{node}: unsupported runtime capabilities: {reasons}")
    disabled_features = require_list(node, data, "disabled_features")
    if any(not isinstance(item, str) or not item.strip() for item in disabled_features):
        raise WorkflowValidationError(f"{node}: disabled_features must contain non-empty strings")
    if "enemy_encounter" in runtime_features and "enemy_encounter" in disabled_features:
        raise WorkflowValidationError(f"{node}: enemy_encounter cannot be both enabled and disabled")
    for mi, mapping in enumerate(require_list(node, data, "mappings", non_empty=True)):
        if not isinstance(mapping, dict):
            raise WorkflowValidationError(f"{node}: mappings[{mi}] must be object")
        for key in ("entity_id", "ability_id", "behavior_id", "flow_id", "runtime_owner", "selected_runtime_owner", "ability_binding"):
            require_string(node, mapping, key, non_empty=True)
        validate_ts_path(node, mapping["runtime_owner"], label=f"mappings[{mi}].runtime_owner")
        carrier = require_string(node, mapping, "implementation_carrier", non_empty=True)
        if carrier not in ALLOWED_CARRIERS:
            raise WorkflowValidationError(f"{node}: invalid implementation_carrier: {carrier}")
        require_list(node, mapping, "thin_contracts", non_empty=True)
        require_list(node, mapping, "verification_evidence", non_empty=True)
        require_list(node, mapping, "existing_framework_candidates")
        require_string(node, mapping, "why_not_existing_framework", non_empty=True)
        require_string(node, mapping, "temporary_or_canonical", non_empty=True)
        require_string(node, mapping, "migration_path", non_empty=True)
        for pi, port in enumerate(require_list(node, mapping, "engine_port_mappings", non_empty=True)):
            if not isinstance(port, dict):
                raise WorkflowValidationError(f"{node}: engine_port_mappings[{pi}] must be object")
            require_string(node, port, "engine_port_id", non_empty=True)
            validate_json_path(node, require_string(node, port, "adjudication_path", non_empty=True), label=f"engine_port_mappings[{pi}].adjudication_path")
            require_string(node, port, "adapter_or_helper", non_empty=True)
            if require_string(node, port, "verdict", non_empty=True) not in ALLOWED_VERDICTS:
                raise WorkflowValidationError(f"{node}: invalid engine port verdict")
            require_list(node, port, "evidence_symbols")
    blocked = require_list(node, data, "blocked_mappings")
    if blocked:
        raise WorkflowValidationError(f"{node}: blocked_mappings must be empty for supported runtime mapping")
