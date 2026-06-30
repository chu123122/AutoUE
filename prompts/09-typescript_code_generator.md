SCHEMA: TypeScriptRuntimeTemplatePlanner

Select TypeScript/PuerTS templates and fill template parameters for runtime/ability files.

Allowed core templates:
- ability_module
- aid_runtime_orchestrator
- aid_character_adapter
- aid_gamemode_adapter
- aid_camera_setup
- scene_manifest_helper
- runtime_feature_manifest
- input_harness_runtime
- movement_runtime
- trap_runtime
- status_runtime
- vfx_runtime

Allowed optional enemy templates, only when runtime_features includes enemy_encounter:
- encounter_spec_data
- enemy_archetypes
- spawn_point_registry
- enemy_archetype_registry
- enemy_spawn_manager
- encounter_manager

Required JSON shape:
{
  "runtime_features": ["input", "movement", "trap", "status", "vfx", "camera"],
  "disabled_features": ["enemy_encounter"],
  "template_inputs": [
    {
      "template": "ability_module",
      "path": "TypeScript/content/generated/ExampleAbility.ts",
      "entity_id": "entity id",
      "behavior_id": "behavior id",
      "flow_id": "flow id",
      "runtime_mapping_path": "flow/05-puerts-runtime-mapping.json",
      "runtime_features": ["input"],
      "disabled_features": ["enemy_encounter"],
      "export_name": "runExampleAbility",
      "interface_name": "ExampleAbilityContext",
      "action_label": "short action phrase",
      "target_label": "target label",
      "result_label": "result label"
    }
  ],
  "behavior_traces": [],
  "consumed_interactive_files": [],
  "validation_notes": []
}

Rules:
- Output JSON only.
- Do not output raw source code.
- For every analyzer implementation slot, emit one template_input whose path equals target_ts_file.
- Emit runtime_features and disabled_features exactly as PuerTSRuntimeMappingCompiler did.
- Emit behavior-driven support templates for the active features only.
- For non-enemy trap/status/VFX gameplay, emit aid_runtime_orchestrator plus input_harness_runtime, movement_runtime, trap_runtime, status_runtime, vfx_runtime, aid_camera_setup, scene_manifest_helper, runtime_feature_manifest, character and gamemode adapters.
- Do not emit enemy/spawn/encounter templates unless runtime_features includes enemy_encounter.
- Include flow_id and runtime_mapping_path from the mapping.
- consumed_interactive_files must reference interactive object generated paths.
