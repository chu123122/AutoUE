from __future__ import annotations

from typing import Any, Mapping

from core.workflow_validation import parse_node_json

RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
SLOT_NODE = "TypeScriptImplementationSlotProjector"
INTERACTIVE_NODE = "TypeScriptInteractiveTemplatePlanner"
BEHAVIOR_SPEC_TS = "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts"

TemplateRow = tuple[str, str, str, str]

BEHAVIOR_SPEC_TEMPLATE: TemplateRow = (
    "behavior_spec_generated",
    BEHAVIOR_SPEC_TS,
    "getAutoUEBehaviorSpec",
    "AutoUEBehaviorSpecContext",
)

CORE_TEMPLATES: list[TemplateRow] = [
    ("world_adapter", "TypeScript/content/generated/AutoUEWorldAdapter.ts", "createAutoUEWorldAdapter", "AutoUEWorldAdapterContext"),
    ("entity_registry", "TypeScript/content/generated/AutoUEEntityRegistry.ts", "createAutoUEEntityRegistry", "AutoUEEntityRegistryContext"),
    ("state_blackboard", "TypeScript/content/generated/AutoUEStateBlackboard.ts", "createAutoUEStateBlackboard", "AutoUEStateBlackboardContext"),
    ("condition_checker", "TypeScript/content/generated/AutoUEConditionChecker.ts", "createAutoUEConditionChecker", "AutoUEConditionCheckerContext"),
    ("action_dispatcher", "TypeScript/content/generated/AutoUEActionDispatcher.ts", "createAutoUEActionDispatcher", "AutoUEActionDispatcherContext"),
    ("runtime_feature_manifest", "TypeScript/content/generated/AutoUERuntimeFeatureManifest.ts", "getAutoUERuntimeFeatureManifest", "AutoUERuntimeFeatureManifestContext"),
    ("scene_manifest_helper", "TypeScript/content/generated/AutoUEGeneratedSceneManifest.ts", "getAutoUEGeneratedSceneManifest", "AutoUEGeneratedSceneManifestContext"),
    ("input_harness_runtime", "TypeScript/content/generated/AutoUEInputHarnessRuntime.ts", "createAutoUEInputHarnessRuntime", "AutoUEInputHarnessRuntimeContext"),
    ("movement_runtime", "TypeScript/content/generated/AutoUEMovementRuntime.ts", "createAutoUEMovementRuntime", "AutoUEMovementRuntimeContext"),
    ("behavior_orchestrator", "TypeScript/content/generated/AutoUEGeneratedRuntime.ts", "createAutoUEBehaviorOrchestrator", "AutoUEBehaviorOrchestratorContext"),
    ("runtime_bootstrap", "TypeScript/content/generated/AutoUERuntimeBootstrap.ts", "bootstrapAutoUEBehaviorRuntime", "AutoUERuntimeBootstrapContext"),
    ("aid_character_adapter", "TypeScript/AutoUEGeneratedCharacterAdapter.ts", "AutoUEGeneratedCharacterAdapter", "AutoUEGeneratedCharacterAdapterContext"),
    ("aid_gamemode_adapter", "TypeScript/AutoUEGeneratedGameModeAdapter.ts", "AutoUEGeneratedGameModeAdapter", "AutoUEGeneratedGameModeAdapterContext"),
]

OPTIONAL_TEMPLATES: list[TemplateRow] = [
    ("trigger_router", "TypeScript/content/generated/AutoUETriggerRouter.ts", "createAutoUETriggerRouter", "AutoUETriggerRouterContext"),
    ("trap_runtime", "TypeScript/content/generated/AutoUETrapRuntime.ts", "createAutoUETrapRuntime", "AutoUETrapRuntimeContext"),
    ("vfx_runtime", "TypeScript/content/generated/AutoUEVfxRuntime.ts", "createAutoUEVfxRuntime", "AutoUEVfxRuntimeContext"),
    ("aid_camera_setup", "TypeScript/content/generated/AutoUEGeneratedCameraHelper.ts", "setupAutoUEGeneratedCamera", "AutoUEGeneratedCameraOptions"),
]

ENEMY_RUNTIME_TEMPLATES: list[TemplateRow] = [
    ("encounter_spec_data", "TypeScript/content/generated/AutoUEGeneratedEncounterSpec.ts", "getAutoUEGeneratedEncounterSpec", "AutoUEGeneratedEncounterSpecContext"),
    ("spawn_point_registry", "TypeScript/content/generated/AutoUESpawnPointRegistry.ts", "createAutoUESpawnPointRegistry", "AutoUESpawnPointRegistryContext"),
    ("enemy_spawn_manager", "TypeScript/content/generated/AutoUEEnemySpawnManager.ts", "createAutoUEEnemySpawnManager", "AutoUEEnemySpawnManagerContext"),
    ("enemy_registry", "TypeScript/content/generated/AutoUEEnemyRegistry.ts", "createAutoUEEnemyRegistry", "AutoUEEnemyRegistryContext"),
    ("enemy_spawn_runtime", "TypeScript/content/generated/AutoUEEnemySpawnRuntime.ts", "createAutoUEEnemySpawnRuntime", "AutoUEEnemySpawnRuntimeContext"),
    ("enemy_brain", "TypeScript/content/generated/AutoUEEnemyBrain.ts", "createAutoUEEnemyBrain", "AutoUEEnemyBrainContext"),
    ("enemy_perception", "TypeScript/content/generated/AutoUEEnemyPerception.ts", "createAutoUEEnemyPerception", "AutoUEEnemyPerceptionContext"),
    ("enemy_movement", "TypeScript/content/generated/AutoUEEnemyMovement.ts", "createAutoUEEnemyMovement", "AutoUEEnemyMovementContext"),
    ("enemy_combat", "TypeScript/content/generated/AutoUEEnemyCombat.ts", "createAutoUEEnemyCombat", "AutoUEEnemyCombatContext"),
    ("enemy_presentation_runtime", "TypeScript/content/generated/AutoUEEnemyPresentationRuntime.ts", "createAutoUEEnemyPresentationRuntime", "AutoUEEnemyPresentationRuntimeContext"),
    ("enemy_health", "TypeScript/content/generated/AutoUEEnemyHealth.ts", "createAutoUEEnemyHealth", "AutoUEEnemyHealthContext"),
    ("enemy_death_events", "TypeScript/content/generated/AutoUEEnemyDeathEvents.ts", "createAutoUEEnemyDeathEvents", "AutoUEEnemyDeathEventsContext"),
    ("enemy_ability_dispatcher", "TypeScript/content/generated/AutoUEEnemyAbilityDispatcher.ts", "createAutoUEEnemyAbilityDispatcher", "AutoUEEnemyAbilityDispatcherContext"),
    ("enemy_projectile_runtime", "TypeScript/content/generated/AutoUEEnemyProjectileRuntime.ts", "createAutoUEEnemyProjectileRuntime", "AutoUEEnemyProjectileRuntimeContext"),
    ("enemy_encounter_manager", "TypeScript/content/generated/AutoUEEncounterManager.ts", "createAutoUEEncounterManager", "AutoUEEncounterManagerContext"),
]

PRIMITIVE_RUNTIME_TEMPLATES: list[TemplateRow] = [
    ("player_movement_runtime", "TypeScript/content/generated/AutoUEPlayerMovementRuntime.ts", "createAutoUEPlayerMovementRuntime", "AutoUEPlayerMovementRuntimeContext"),
    ("player_combat_runtime", "TypeScript/content/generated/AutoUEPlayerCombatRuntime.ts", "createAutoUEPlayerCombatRuntime", "AutoUEPlayerCombatRuntimeContext"),
    ("hit_query_runtime", "TypeScript/content/generated/AutoUEHitQueryRuntime.ts", "createAutoUEHitQueryRuntime", "AutoUEHitQueryRuntimeContext"),
    ("damage_runtime", "TypeScript/content/generated/AutoUEDamageRuntime.ts", "createAutoUEDamageRuntime", "AutoUEDamageRuntimeContext"),
    ("pickup_runtime", "TypeScript/content/generated/AutoUEPickupRuntime.ts", "createAutoUEPickupRuntime", "AutoUEPickupRuntimeContext"),
    ("reward_runtime", "TypeScript/content/generated/AutoUERewardRuntime.ts", "createAutoUERewardRuntime", "AutoUERewardRuntimeContext"),
    ("feedback_runtime", "TypeScript/content/generated/AutoUEFeedbackRuntime.ts", "createAutoUEFeedbackRuntime", "AutoUEFeedbackRuntimeContext"),
]

TEMPLATE_BY_MODULE: dict[str, TemplateRow] = {
    row[0]: row for row in [BEHAVIOR_SPEC_TEMPLATE, *CORE_TEMPLATES, *OPTIONAL_TEMPLATES, *ENEMY_RUNTIME_TEMPLATES, *PRIMITIVE_RUNTIME_TEMPLATES]
}
TEMPLATE_BY_MODULE["encounter_manager"] = TEMPLATE_BY_MODULE["enemy_encounter_manager"]
TEMPLATE_BY_MODULE["enemy_runtime"] = TEMPLATE_BY_MODULE["enemy_registry"]
TEMPLATE_BY_MODULE["enemy_presentation"] = TEMPLATE_BY_MODULE["enemy_presentation_runtime"]

ENEMY_CLUSTER = {row[0] for row in ENEMY_RUNTIME_TEMPLATES}
CORE_ALWAYS = [
    "behavior_spec_generated",
    "world_adapter",
    "entity_registry",
    "state_blackboard",
    "condition_checker",
    "action_dispatcher",
    "runtime_feature_manifest",
    "scene_manifest_helper",
    "input_harness_runtime",
    "movement_runtime",
    "behavior_orchestrator",
    "runtime_bootstrap",
    "aid_character_adapter",
    "aid_gamemode_adapter",
]

IMPORT_DEPS: dict[str, set[str]] = {
    "behavior_orchestrator": {"behavior_spec_generated", "scene_manifest_helper", "input_harness_runtime", "movement_runtime", "state_blackboard", "world_adapter"},
    "aid_character_adapter": {"behavior_orchestrator"},
    "player_combat_runtime": {"hit_query_runtime"},
    "hit_query_runtime": {"world_adapter"},
    "damage_runtime": {"world_adapter"},
    "enemy_spawn_runtime": {"world_adapter", "enemy_registry"},
    "enemy_spawn_manager": {"spawn_point_registry", "enemy_spawn_runtime", "enemy_registry"},
    "enemy_encounter_manager": {"enemy_spawn_manager", "enemy_registry"},
    "enemy_brain": {"enemy_registry", "enemy_perception", "enemy_ability_dispatcher", "world_adapter"},
    "enemy_perception": {"world_adapter", "enemy_registry"},
    "enemy_movement": {"world_adapter", "enemy_registry"},
    "enemy_combat": {"world_adapter", "enemy_registry", "enemy_death_events", "enemy_presentation_runtime"},
    "enemy_presentation_runtime": {"world_adapter"},
    "enemy_health": {"world_adapter", "enemy_registry", "enemy_death_events", "enemy_presentation_runtime"},
    "enemy_death_events": {"world_adapter", "enemy_registry", "enemy_encounter_manager", "enemy_presentation_runtime"},
    "enemy_ability_dispatcher": {"enemy_spawn_runtime", "enemy_perception", "enemy_movement", "enemy_combat", "enemy_health", "enemy_death_events", "enemy_encounter_manager"},
}


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


def _ordered_add(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _expand_template_modules(runtime_features: list[str]) -> list[str]:
    modules: list[str] = []
    for module in CORE_ALWAYS:
        _ordered_add(modules, module)
    for feature in runtime_features:
        if feature == "enemy_runtime":
            for module in ENEMY_CLUSTER:
                _ordered_add(modules, module)
            continue
        mapped = TEMPLATE_BY_MODULE.get(feature)
        if mapped:
            _ordered_add(modules, mapped[0])
    changed = True
    while changed:
        changed = False
        for module in list(modules):
            for dep in IMPORT_DEPS.get(module, set()):
                if dep not in modules:
                    modules.append(dep)
                    changed = True
    return [m for m in modules if m in TEMPLATE_BY_MODULE]


def _template_inputs(modules: list[str], base: Mapping[str, Any]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for module in modules:
        template, path, export, iface = TEMPLATE_BY_MODULE[module]
        if template in seen:
            continue
        seen.add(template)
        inputs.append({"template": template, "path": path, "export_name": export, "interface_name": iface, **base})
    return inputs


def _blocked_capabilities(support: Mapping[str, Any]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for key in ("unsupported_capabilities", "unsupported_primitives"):
        for item in support.get(key, []) if isinstance(support, Mapping) else []:
            if isinstance(item, Mapping):
                blocked.append(dict(item))
    return blocked


def run_typescript_runtime_template_plan(inputs: dict[str, str]) -> dict[str, Any]:
    mapping = parse_node_json(RUNTIME_NODE, inputs.get("runtime_mapping", ""))
    analyzer = parse_node_json(SLOT_NODE, inputs.get("ts_slots", ""))
    interactive = parse_node_json(INTERACTIVE_NODE, inputs.get("interactive_ts_plan", ""))
    support = mapping.get("support_check", {})
    spec = mapping.get("behavior_spec", {})
    encounter_spec = mapping.get("encounter_spec", {})
    first = _first_behavior(spec)
    runtime_features = list(mapping.get("runtime_features", []))
    disabled_features = list(mapping.get("disabled_features", []))
    blocked = _blocked_capabilities(support)
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
        "encounter_spec": encounter_spec,
        "encounter_spec_path": mapping.get("encounter_spec_path"),
        "scene_spawn_manifest_path": mapping.get("scene_spawn_manifest_path"),
        "support_check": support,
    }
    rendered_modules = _expand_template_modules(runtime_features)
    template_inputs = _template_inputs(rendered_modules, base)

    rendered_paths = {item["path"] for item in template_inputs}
    for slot in analyzer.get("implementation_slots", []) if isinstance(analyzer, Mapping) else []:
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
    for behavior in spec.get("behaviors", []) if isinstance(spec, Mapping) else []:
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
    notes = ["module-driven behavior runtime framework rendered", "raw TypeScript content is forbidden"]
    if blocked:
        notes.append("unsupported capabilities were blocked and reported; supported runtime modules still rendered")
    return {
        "runtime_features": runtime_features,
        "disabled_features": disabled_features,
        "support_check": support,
        "behavior_spec": spec,
        "encounter_spec": encounter_spec,
        "rendered_runtime_modules": rendered_modules,
        "rendered_template_closure": [item["template"] for item in template_inputs],
        "blocked_capabilities": blocked,
        "template_inputs": template_inputs,
        "behavior_traces": traces,
        "consumed_interactive_files": _interactive_files(interactive),
        "validation_notes": notes,
    }
