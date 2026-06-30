SCHEMA: TypeScriptCodeGenerator

Select TypeScript/PuerTS templates and fill template parameters for runtime/ability files.

Allowed templates:
- ability_module
- runtime_bootstrap
- aid_runtime_orchestrator
- aid_character_adapter
- aid_gamemode_adapter
- aid_camera_setup
- scene_manifest_helper
- encounter_spec_data
- enemy_archetypes
- spawn_point_registry
- enemy_archetype_registry
- enemy_spawn_manager
- encounter_manager

Required JSON shape:
{
  "template_inputs": [
    {
      "template": "ability_module",
      "path": "TypeScript/content/generated/ExampleAbility.ts",
      "entity_id": "entity id",
      "behavior_id": "behavior id",
      "flow_id": "flow id",
      "runtime_mapping_path": "flow/05-puerts-runtime-mapping.json",
      "export_name": "runExampleAbility",
      "interface_name": "ExampleAbilityContext",
      "action_label": "short action phrase",
      "target_label": "target label",
      "result_label": "result label"
    }
  ],
  "behavior_traces": [
    {
      "entity_id": "entity id",
      "behavior_id": "behavior id",
      "flow_id": "flow id",
      "runtime_mapping_path": "flow/05-puerts-runtime-mapping.json",
      "file_path": "TypeScript/content/generated/ExampleAbility.ts",
      "export_name": "runExampleAbility"
    }
  ],
  "consumed_interactive_files": ["TypeScript/content/generated/interactive/ExampleInteractable.ts"],
  "validation_notes": []
}

Rules:
- Output JSON only.
- Do not output raw source code.
- For every analyzer implementation slot, emit one template_input whose path equals target_ts_file.
- Additionally emit all support template_inputs for the runnable AIDev bridge:
  - aid_runtime_orchestrator -> TypeScript/content/generated/AutoUEGeneratedRuntime.ts, export_name runAutoUEGeneratedRuntime, interface_name AutoUEGeneratedRuntimeContext
  - aid_character_adapter -> TypeScript/AutoUEGeneratedCharacterAdapter.ts, export_name AutoUEGeneratedCharacterAdapter, interface_name AutoUEGeneratedCharacterAdapterContext
  - aid_gamemode_adapter -> TypeScript/AutoUEGeneratedGameModeAdapter.ts, export_name AutoUEGeneratedGameModeAdapter, interface_name AutoUEGeneratedGameModeAdapterContext
  - aid_camera_setup -> TypeScript/content/generated/AutoUEGeneratedCameraHelper.ts, export_name setupAutoUEGeneratedCamera, interface_name AutoUEGeneratedCameraOptions
  - scene_manifest_helper -> TypeScript/content/generated/AutoUEGeneratedSceneManifest.ts, export_name getAutoUEGeneratedSceneManifest, interface_name AutoUEGeneratedSceneManifestContext
  - encounter_spec_data -> TypeScript/content/generated/AutoUEGeneratedEncounterSpec.ts, export_name getAutoUEGeneratedEncounterSpec, interface_name AutoUEGeneratedEncounterSpecContext
  - enemy_archetypes -> TypeScript/content/generated/AutoUEGeneratedEnemyArchetypes.ts, export_name getAutoUEGeneratedEnemyArchetypes, interface_name AutoUEGeneratedEnemyArchetypesContext
  - spawn_point_registry -> TypeScript/content/generated/AutoUESpawnPointRegistry.ts, export_name createAutoUESpawnPointRegistry, interface_name AutoUESpawnPointRegistryContext
  - enemy_archetype_registry -> TypeScript/content/generated/AutoUEEnemyArchetypeRegistry.ts, export_name createAutoUEEnemyArchetypeRegistry, interface_name AutoUEEnemyArchetypeRegistryContext
  - enemy_spawn_manager -> TypeScript/content/generated/AutoUEEnemySpawnManager.ts, export_name createAutoUEEnemySpawnManager, interface_name AutoUEEnemySpawnManagerContext
  - encounter_manager -> TypeScript/content/generated/AutoUEEncounterManager.ts, export_name createAutoUEEncounterManager, interface_name AutoUEEncounterManagerContext
- Support template_inputs still need entity_id, behavior_id, flow_id, runtime_mapping_path, interface_name, action_label, target_label, and result_label; use the most central gameplay behavior as the trace anchor.
- TypeScriptCodeGenerator must consume EncounterSpecPlanner as data. It may generate glue, but must not invent enemy ids or spawn groups beyond EncounterSpec.
- The AIDev bridge support templates are responsible for runnable runtime orchestration, including application-layer input harness tags (`AUTOUE_INPUT_RIGHT_1S`, `AUTOUE_INPUT_ATTACK`), one-shot ice-trap freeze/rearm behavior, freeze VFX visibility, side-camera setup, camera feedback shake, real spawn point scanning, real `BP_AutoUECombatEnemy` spawning, alive enemy registration, and snapshot-friendly state tags. Do not create extra LLM nodes for these bridge concerns.
- Include flow_id and runtime_mapping_path from the mapping.
- consumed_interactive_files must reference interactive object generated paths.
