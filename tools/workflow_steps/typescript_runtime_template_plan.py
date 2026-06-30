from __future__ import annotations

from typing import Any, Mapping

from core.workflow_validation import parse_node_json

RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
SLOT_NODE = "TypeScriptImplementationSlotProjector"
INTERACTIVE_NODE = "TypeScriptInteractiveTemplatePlanner"
BEHAVIOR_SPEC_TS = "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts"
FRAMEWORK_TEMPLATES = [
    ("world_adapter", "TypeScript/content/generated/AutoUEWorldAdapter.ts", "createAutoUEWorldAdapter", "AutoUEWorldAdapterContext"),
    ("entity_registry", "TypeScript/content/generated/AutoUEEntityRegistry.ts", "createAutoUEEntityRegistry", "AutoUEEntityRegistryContext"),
    ("state_blackboard", "TypeScript/content/generated/AutoUEStateBlackboard.ts", "createAutoUEStateBlackboard", "AutoUEStateBlackboardContext"),
    ("trigger_router", "TypeScript/content/generated/AutoUETriggerRouter.ts", "createAutoUETriggerRouter", "AutoUETriggerRouterContext"),
    ("condition_checker", "TypeScript/content/generated/AutoUEConditionChecker.ts", "createAutoUEConditionChecker", "AutoUEConditionCheckerContext"),
    ("action_dispatcher", "TypeScript/content/generated/AutoUEActionDispatcher.ts", "createAutoUEActionDispatcher", "AutoUEActionDispatcherContext"),
    ("runtime_feature_manifest", "TypeScript/content/generated/AutoUERuntimeFeatureManifest.ts", "getAutoUERuntimeFeatureManifest", "AutoUERuntimeFeatureManifestContext"),
    ("input_harness_runtime", "TypeScript/content/generated/AutoUEInputHarnessRuntime.ts", "createAutoUEInputHarnessRuntime", "AutoUEInputHarnessRuntimeContext"),
    ("movement_runtime", "TypeScript/content/generated/AutoUEMovementRuntime.ts", "createAutoUEMovementRuntime", "AutoUEMovementRuntimeContext"),
    ("trap_runtime", "TypeScript/content/generated/AutoUETrapRuntime.ts", "createAutoUETrapRuntime", "AutoUETrapRuntimeContext"),
    ("vfx_runtime", "TypeScript/content/generated/AutoUEVfxRuntime.ts", "createAutoUEVfxRuntime", "AutoUEVfxRuntimeContext"),
    ("aid_camera_setup", "TypeScript/content/generated/AutoUEGeneratedCameraHelper.ts", "setupAutoUEGeneratedCamera", "AutoUEGeneratedCameraOptions"),
    ("scene_manifest_helper", "TypeScript/content/generated/AutoUEGeneratedSceneManifest.ts", "getAutoUEGeneratedSceneManifest", "AutoUEGeneratedSceneManifestContext"),
    ("behavior_orchestrator", "TypeScript/content/generated/AutoUEGeneratedRuntime.ts", "createAutoUEBehaviorOrchestrator", "AutoUEBehaviorOrchestratorContext"),
    ("runtime_bootstrap", "TypeScript/content/generated/AutoUERuntimeBootstrap.ts", "bootstrapAutoUEBehaviorRuntime", "AutoUERuntimeBootstrapContext"),
    ("aid_character_adapter", "TypeScript/AutoUEGeneratedCharacterAdapter.ts", "AutoUEGeneratedCharacterAdapter", "AutoUEGeneratedCharacterAdapterContext"),
    ("aid_gamemode_adapter", "TypeScript/AutoUEGeneratedGameModeAdapter.ts", "AutoUEGeneratedGameModeAdapter", "AutoUEGeneratedGameModeAdapterContext"),
]
ENEMY_RUNTIME_TEMPLATES = [
    ("enemy_registry", "TypeScript/content/generated/AutoUEEnemyRegistry.ts", "createAutoUEEnemyRegistry", "AutoUEEnemyRegistryContext"),
    ("enemy_spawn_runtime", "TypeScript/content/generated/AutoUEEnemySpawnRuntime.ts", "createAutoUEEnemySpawnRuntime", "AutoUEEnemySpawnRuntimeContext"),
    ("enemy_brain", "TypeScript/content/generated/AutoUEEnemyBrain.ts", "createAutoUEEnemyBrain", "AutoUEEnemyBrainContext"),
    ("enemy_perception", "TypeScript/content/generated/AutoUEEnemyPerception.ts", "createAutoUEEnemyPerception", "AutoUEEnemyPerceptionContext"),
    ("enemy_movement", "TypeScript/content/generated/AutoUEEnemyMovement.ts", "createAutoUEEnemyMovement", "AutoUEEnemyMovementContext"),
    ("enemy_combat", "TypeScript/content/generated/AutoUEEnemyCombat.ts", "createAutoUEEnemyCombat", "AutoUEEnemyCombatContext"),
    ("enemy_health", "TypeScript/content/generated/AutoUEEnemyHealth.ts", "createAutoUEEnemyHealth", "AutoUEEnemyHealthContext"),
    ("enemy_death_events", "TypeScript/content/generated/AutoUEEnemyDeathEvents.ts", "createAutoUEEnemyDeathEvents", "AutoUEEnemyDeathEventsContext"),
    ("enemy_ability_dispatcher", "TypeScript/content/generated/AutoUEEnemyAbilityDispatcher.ts", "createAutoUEEnemyAbilityDispatcher", "AutoUEEnemyAbilityDispatcherContext"),
    ("enemy_projectile_runtime", "TypeScript/content/generated/AutoUEEnemyProjectileRuntime.ts", "createAutoUEEnemyProjectileRuntime", "AutoUEEnemyProjectileRuntimeContext"),
    ("enemy_encounter_manager", "TypeScript/content/generated/AutoUEEncounterManager.ts", "createAutoUEEncounterManager", "AutoUEEncounterManagerContext"),
]


def _first_behavior(spec: Mapping[str, Any]) -> dict[str, Any]:
    behaviors = spec.get("behaviors", []) if isinstance(spec, Mapping) else []
    if not behaviors or not isinstance(behaviors[0], Mapping):
        raise RuntimeError("TypeScriptRuntimeTemplatePlanner requires at least one BehaviorSpec behavior")
    return dict(behaviors[0])


def _interactive_files(interactive: Mapping[str, Any]) -> list[str]:
    files: list[str] = []
    for item in interactive.get("template_inputs", []) if isinstance(interactive, Mapping) else []:
        if isinstance(item, Mapping) and isinstance(item.get("path"), str):
            files.append(str(item["path"]))
    return files


def run_typescript_runtime_template_plan(inputs: dict[str, str]) -> dict[str, Any]:
    mapping = parse_node_json(RUNTIME_NODE, inputs.get("runtime_mapping", ""))
    analyzer = parse_node_json(SLOT_NODE, inputs.get("ts_slots", ""))
    interactive = parse_node_json(INTERACTIVE_NODE, inputs.get("interactive_ts_plan", ""))
    support = mapping.get("support_check", {})
    if support.get("status") != "supported":
        reasons = [item.get("reason", "") for item in support.get("unsupported_capabilities", []) if isinstance(item, Mapping)]
        raise RuntimeError(f"TypeScriptRuntimeTemplatePlanner refuses unsupported BehaviorSpec: {reasons}")
    spec = mapping.get("behavior_spec", {})
    first = _first_behavior(spec)
    runtime_features = list(mapping.get("runtime_features", []))
    disabled_features = list(mapping.get("disabled_features", []))
    base = {
        "entity_id": first.get("entity_id") or first.get("primary_entity_id"),
        "behavior_id": first.get("behavior_id"),
        "flow_id": first.get("flow_id"),
        "runtime_mapping_path": mapping.get("runtime_mapping_path"),
        "action_label": "execute BehaviorSpec action chain",
        "target_label": "BehaviorSpec",
        "result_label": "runtime framework dispatches data actions",
        "runtime_features": runtime_features,
        "disabled_features": disabled_features,
        "behavior_spec": spec,
        "support_check": support,
    }
    template_inputs = [{
        "template": "behavior_spec_generated",
        "path": BEHAVIOR_SPEC_TS,
        "export_name": "getAutoUEBehaviorSpec",
        "interface_name": "AutoUEBehaviorSpecContext",
        **base,
    }]
    for template, path, export, iface in FRAMEWORK_TEMPLATES:
        template_inputs.append({"template": template, "path": path, "export_name": export, "interface_name": iface, **base})
    if "enemy_runtime" in runtime_features:
        for template, path, export, iface in ENEMY_RUNTIME_TEMPLATES:
            template_inputs.append({"template": template, "path": path, "export_name": export, "interface_name": iface, **base})

    rendered_paths = {item["path"] for item in template_inputs}
    for slot in analyzer.get("implementation_slots", []):
        target = slot.get("target_ts_file") if isinstance(slot, Mapping) else None
        if isinstance(target, str) and target and target not in rendered_paths:
            template_inputs.append({
                "template": "behavior_spec_generated",
                "path": target,
                "export_name": "getAutoUEBehaviorSpec",
                "interface_name": "AutoUEBehaviorSpecContext",
                **base,
            })
            rendered_paths.add(target)

    traces = []
    for behavior in spec.get("behaviors", []):
        if not isinstance(behavior, Mapping):
            continue
        traces.append({
            "entity_id": behavior.get("entity_id") or behavior.get("primary_entity_id"),
            "behavior_id": behavior.get("behavior_id"),
            "flow_id": behavior.get("flow_id"),
            "runtime_mapping_path": mapping.get("runtime_mapping_path"),
            "file_path": BEHAVIOR_SPEC_TS,
            "export_name": "getAutoUEBehaviorSpec",
        })
    return {
        "runtime_features": runtime_features,
        "disabled_features": disabled_features,
        "support_check": support,
        "template_inputs": template_inputs,
        "behavior_traces": traces,
        "consumed_interactive_files": _interactive_files(interactive),
        "validation_notes": ["shared behavior runtime framework rendered", "raw TypeScript content is forbidden"],
    }
