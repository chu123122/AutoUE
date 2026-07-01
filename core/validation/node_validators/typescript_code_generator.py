"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import WorkflowValidationError, require_list, validate_ts_path
from core.validation.node_validators.typescript_interactive_object_generator import _reject_raw_files, _template_inputs, _traces

ENEMY_TEMPLATES = {
    "enemy_archetypes",
    "spawn_point_registry",
    "enemy_archetype_registry",
    "enemy_spawn_manager",
    "encounter_manager",
    "encounter_spec_data",
    "enemy_registry",
    "enemy_spawn_runtime",
    "enemy_brain",
    "enemy_perception",
    "enemy_movement",
    "enemy_combat",
    "enemy_health",
    "enemy_death_events",
    "enemy_ability_dispatcher",
    "enemy_projectile_runtime",
    "enemy_encounter_manager",
}
REQUIRED_ENEMY_RUNTIME_TEMPLATES = {
    "encounter_spec_data",
    "spawn_point_registry",
    "enemy_spawn_manager",
    "enemy_registry",
    "enemy_spawn_runtime",
    "enemy_brain",
    "enemy_perception",
    "enemy_movement",
    "enemy_combat",
    "enemy_health",
    "enemy_death_events",
    "enemy_ability_dispatcher",
    "enemy_encounter_manager",
}

PRIMITIVE_MODULE_TEMPLATES = {
    "player_movement_runtime": "player_movement_runtime",
    "player_combat_runtime": "player_combat_runtime",
    "hit_query_runtime": "hit_query_runtime",
    "damage_runtime": "damage_runtime",
    "pickup_runtime": "pickup_runtime",
    "reward_runtime": "reward_runtime",
    "feedback_runtime": "feedback_runtime",
}


def validate_typescript_code_generator(node: str, data: dict[str, Any]) -> None:
    _reject_raw_files(node, data)
    runtime_features = require_list(node, data, "runtime_features", non_empty=True)
    if any(not isinstance(item, str) or not item.strip() for item in runtime_features):
        raise WorkflowValidationError(f"{node}: runtime_features must contain non-empty strings")
    if any(item in {"status", "interaction"} for item in runtime_features):
        raise WorkflowValidationError(f"{node}: runtime_features must not contain status/interaction")
    disabled_features = require_list(node, data, "disabled_features")
    if any(not isinstance(item, str) or not item.strip() for item in disabled_features):
        raise WorkflowValidationError(f"{node}: disabled_features must contain non-empty strings")
    if "enemy_encounter" in runtime_features and "enemy_encounter" in disabled_features:
        raise WorkflowValidationError(f"{node}: enemy_encounter cannot be both enabled and disabled")
    template_names = {item.get("template", "") for item in data.get("template_inputs", []) if isinstance(item, dict)}
    enemy_templates = sorted(template_names.intersection(ENEMY_TEMPLATES))
    if enemy_templates and "enemy_runtime" not in runtime_features:
        raise WorkflowValidationError(f"{node}: enemy templates require runtime_features to include enemy_runtime: {enemy_templates}")
    if "enemy_runtime" in runtime_features:
        missing = sorted(REQUIRED_ENEMY_RUNTIME_TEMPLATES - template_names)
        if missing:
            raise WorkflowValidationError(f"{node}: enemy_runtime requires templates: {missing}")
        support_check = data.get("support_check", {})
        blocked = data.get("blocked_capabilities", [])
        if not isinstance(support_check, dict):
            raise WorkflowValidationError(f"{node}: enemy_runtime requires support_check")
        if support_check.get("status") != "supported" and not blocked:
            raise WorkflowValidationError(f"{node}: unsupported enemy_runtime must report blocked_capabilities")
        behavior_spec = data.get("behavior_spec", {})
        encounter_spec = data.get("encounter_spec", {})
        if not isinstance(encounter_spec, dict) or encounter_spec.get("schema_version") != "autoue-encounter-spec/v1":
            raise WorkflowValidationError(f"{node}: enemy_runtime requires generated autoue-encounter-spec/v1 data")
        encounters = encounter_spec.get("encounters", [])
        if isinstance(encounters, list) and encounters:
            paths_by_template = {item.get("template", ""): item.get("path", "") for item in data.get("template_inputs", []) if isinstance(item, dict)}
            required_paths = {
                "encounter_spec_data": "TypeScript/content/generated/AutoUEGeneratedEncounterSpec.ts",
                "spawn_point_registry": "TypeScript/content/generated/AutoUESpawnPointRegistry.ts",
                "enemy_spawn_manager": "TypeScript/content/generated/AutoUEEnemySpawnManager.ts",
                "enemy_encounter_manager": "TypeScript/content/generated/AutoUEEncounterManager.ts",
            }
            for template, expected_path in required_paths.items():
                if paths_by_template.get(template) != expected_path:
                    raise WorkflowValidationError(f"{node}: EncounterSpec runtime template {template} must emit {expected_path}")
        for behavior in behavior_spec.get("behaviors", []) if isinstance(behavior_spec, dict) else []:
            if not isinstance(behavior, dict) or behavior.get("runtime_domain") != "enemy_runtime":
                continue
            resolved = behavior.get("resolved_capabilities")
            if not isinstance(resolved, list) or not resolved:
                raise WorkflowValidationError(f"{node}: enemy_runtime template input requires resolved_capabilities")
            for capability in resolved:
                capability_id = str(capability.get("capability_id") or "") if isinstance(capability, dict) else ""
                if not capability_id.startswith(("enemy.", "encounter.complete.")):
                    raise WorkflowValidationError(f"{node}: enemy_runtime template input consumed non-canonical capability: {capability_id}")
    missing_primitive_templates = sorted(template for module, template in PRIMITIVE_MODULE_TEMPLATES.items() if module in runtime_features and template not in template_names)
    if missing_primitive_templates:
        raise WorkflowValidationError(f"{node}: primitive runtime modules require templates: {missing_primitive_templates}")
    if any(module in runtime_features for module in PRIMITIVE_MODULE_TEMPLATES):
        support_check = data.get("support_check", {})
        blocked = data.get("blocked_capabilities", [])
        if not isinstance(support_check, dict):
            raise WorkflowValidationError(f"{node}: primitive runtime requires support_check")
        if (support_check.get("status") != "supported" or support_check.get("static_support", "supported") != "supported") and not blocked:
            raise WorkflowValidationError(f"{node}: unsupported primitive runtime must report blocked_capabilities")
        if support_check.get("runtime_proof", "not_run") not in {"not_run", "pass", "fail"}:
            raise WorkflowValidationError(f"{node}: primitive runtime support_check.runtime_proof must be not_run/pass/fail")
        if support_check.get("unsupported_primitives") not in ([], None) and not blocked:
            raise WorkflowValidationError(f"{node}: primitive runtime requires blocked_capabilities for unsupported_primitives")
        behavior_spec = data.get("behavior_spec", {})
        for behavior in behavior_spec.get("behaviors", []) if isinstance(behavior_spec, dict) else []:
            if not isinstance(behavior, dict) or behavior.get("behavior_id") not in {"player.behavior.move_and_attack", "pickup.behavior.collect_reward"}:
                continue
            plan = behavior.get("primitive_plan")
            if not isinstance(plan, list) or not plan:
                raise WorkflowValidationError(f"{node}: primitive runtime template input requires primitive_plan")

    paths = _template_inputs(node, data)
    _traces(node, data, paths)
    for pi, path in enumerate(require_list(node, data, "consumed_interactive_files", non_empty=True)):
        if not isinstance(path, str):
            raise WorkflowValidationError(f"{node}: consumed_interactive_files[{pi}] must be string")
        validate_ts_path(node, path, label=f"consumed_interactive_files[{pi}]")
    require_list(node, data, "validation_notes")
