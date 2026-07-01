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
    validate_json_path(node, require_string(node, data, "encounter_spec_path", non_empty=True), label="encounter_spec_path")
    validate_json_path(node, require_string(node, data, "scene_spawn_manifest_path", non_empty=True), label="scene_spawn_manifest_path")
    behavior_spec = require_dict(node, data, "behavior_spec")
    if behavior_spec.get("schema_version") != "autoue-behavior-spec/v1":
        raise WorkflowValidationError(f"{node}: behavior_spec schema_version must be autoue-behavior-spec/v1")
    support_check = require_dict(node, data, "support_check")
    if support_check.get("status") != "supported" or support_check.get("static_support", "supported") != "supported":
        reasons = [item.get("reason", "") for item in support_check.get("unsupported_capabilities", []) if isinstance(item, dict)]
        reasons += [item.get("reason", "") for item in support_check.get("unsupported_primitives", []) if isinstance(item, dict)]
        raise WorkflowValidationError(f"{node}: unsupported runtime capabilities/primitives: {reasons}")
    if support_check.get("runtime_proof", "not_run") not in {"not_run", "pass", "fail"}:
        raise WorkflowValidationError(f"{node}: support_check.runtime_proof must be not_run/pass/fail")
    if support_check.get("unsupported_primitives") not in ([], None):
        raise WorkflowValidationError(f"{node}: unsupported_primitives must be empty for supported runtime mapping")
    disabled_features = require_list(node, data, "disabled_features")
    if any(not isinstance(item, str) or not item.strip() for item in disabled_features):
        raise WorkflowValidationError(f"{node}: disabled_features must contain non-empty strings")
    if "enemy_encounter" in runtime_features and "enemy_encounter" in disabled_features:
        raise WorkflowValidationError(f"{node}: enemy_encounter cannot be both enabled and disabled")
    encounter_spec = require_dict(node, data, "encounter_spec")
    if encounter_spec.get("schema_version") != "autoue-encounter-spec/v1":
        raise WorkflowValidationError(f"{node}: encounter_spec schema_version must be autoue-encounter-spec/v1")
    encounters = encounter_spec.get("encounters", [])
    has_encounters = any(isinstance(item, dict) for item in encounters) if isinstance(encounters, list) else False
    if has_encounters:
        required_encounter_modules = {"encounter_spec_data", "spawn_point_registry", "enemy_spawn_manager", "encounter_manager", "enemy_spawn_runtime"}
        missing_modules = sorted(required_encounter_modules - set(runtime_features))
        if missing_modules:
            raise WorkflowValidationError(f"{node}: generated EncounterSpec is not fully wired into runtime modules: {missing_modules}")
        if "enemy_runtime" in disabled_features or "enemy_encounter" in disabled_features:
            raise WorkflowValidationError(f"{node}: EncounterSpec with encounters cannot disable enemy runtime/encounter")

    primitive_behaviors = {"player.behavior.move_and_attack", "pickup.behavior.collect_reward"}
    for behavior in behavior_spec.get("behaviors", []):
        if not isinstance(behavior, dict) or behavior.get("behavior_id") not in primitive_behaviors:
            continue
        plan = behavior.get("primitive_plan")
        if not isinstance(plan, list) or not plan:
            raise WorkflowValidationError(f"{node}: {behavior.get('behavior_id')} requires non-empty primitive_plan")
        for si, step in enumerate(plan):
            if not isinstance(step, dict):
                raise WorkflowValidationError(f"{node}: primitive_plan[{si}] must be object")
            require_string(node, step, "primitive_id", non_empty=True)
            require_string(node, step, "handler", non_empty=True)
            modules = require_list(node, step, "required_runtime_modules", non_empty=True)
            if any(not isinstance(item, str) or not item.strip() for item in modules):
                raise WorkflowValidationError(f"{node}: primitive_plan[{si}].required_runtime_modules must contain non-empty strings")
            if not isinstance(step.get("params"), dict):
                raise WorkflowValidationError(f"{node}: primitive_plan[{si}].params must be object")
    if "enemy_runtime" in runtime_features:
        required_modules = {"enemy_registry", "enemy_death_events", "encounter_manager"}
        missing_modules = sorted(required_modules - set(runtime_features))
        if missing_modules:
            raise WorkflowValidationError(f"{node}: enemy_runtime missing required runtime modules: {missing_modules}")
        for behavior in behavior_spec.get("behaviors", []):
            if not isinstance(behavior, dict) or behavior.get("runtime_domain") != "enemy_runtime":
                continue
            resolved = behavior.get("resolved_capabilities")
            if not isinstance(resolved, list) or not resolved:
                raise WorkflowValidationError(f"{node}: enemy_runtime behavior requires resolved_capabilities")
            for capability in resolved:
                if not isinstance(capability, dict):
                    raise WorkflowValidationError(f"{node}: resolved_capabilities entries must be objects")
                capability_id = str(capability.get("capability_id") or "")
                if not capability_id.startswith(("enemy.", "encounter.complete.")):
                    raise WorkflowValidationError(f"{node}: enemy_runtime consumed non-canonical capability: {capability_id}")
                if not capability.get("handler"):
                    raise WorkflowValidationError(f"{node}: resolved capability missing handler: {capability_id}")
                if not isinstance(capability.get("params"), dict):
                    raise WorkflowValidationError(f"{node}: resolved capability missing params: {capability_id}")
            actions = {action.get("type") for action in behavior.get("actions", []) if isinstance(action, dict)}
            if "enemy_spawn_actor" in actions:
                spawn = next((item for item in resolved if isinstance(item, dict) and item.get("capability_id") == "enemy.spawn.spawn_actor"), {})
                params = spawn.get("params", {}) if isinstance(spawn, dict) else {}
                if not isinstance(params, dict) or not params.get("actor_class_path"):
                    raise WorkflowValidationError(f"{node}: enemy_spawn requires actor_class_path in resolved spawn params")
            if "enemy_emit_death_event" in actions and "encounter_complete_when_all_dead" not in actions:
                raise WorkflowValidationError(f"{node}: enemy_death requires alive count trace via encounter completion action")
            if any(action_type in actions for action_type in {"enemy_melee_attack", "enemy_projectile_attack", "enemy_self_destruct"}) and "enemy_receive_damage" not in actions:
                raise WorkflowValidationError(f"{node}: enemy_attack requires enemy health damage path")
    for mi, mapping in enumerate(require_list(node, data, "mappings", non_empty=True)):
        if not isinstance(mapping, dict):
            raise WorkflowValidationError(f"{node}: mappings[{mi}] must be object")
        for key in ("entity_id", "behavior_id", "flow_id", "runtime_owner", "selected_runtime_owner", "ability_binding"):
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
