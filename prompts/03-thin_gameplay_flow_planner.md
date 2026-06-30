SCHEMA: ThinGameplayFlowPlanner

Turn every selected behavior into a thin gameplay flow. This node describes gameplay execution contracts and engine capability ports only.

Required JSON shape:
{
  "flows": [
    {
      "flow_id": "stable_flow_id",
      "entity_id": "entity id from planner",
      "ability_id": "legacy parent capability id from planner output",
      "source_behavior_id": "behavior id from planner",
      "stages": [
        {
          "stage": "Input|Ability/Action|SpatialQuery/HitQuery|Damage/Resource|Event/Result|Feedback/HUD|Cleanup|Custom",
          "contract": "what this stage must do",
          "inputs": [],
          "outputs": [],
          "engine_ports": ["input.action_binding"]
        }
      ],
      "verification": []
    }
  ]
}

Rules:
- Output JSON only.
- Create exactly one flow for every behavior.
- Do not choose TypeScript files.
- Do not write code.
- Treat ability_id as the legacy field name for parent capability_id.
- Use behavior.required_capability_ids and capability.runtime_primitives to choose 1-2 narrow engine_ports per flow.
- engine_ports are query seeds for UE API MCP. Use stable snake/dot ids such as input.action_binding, primitive.on_component_begin_overlap, component.set_visibility, pawn.add_movement_input, camera.update_view_target, gameplay_statics.apply_damage.
- Every flow must have at least one engine_port.
- For non-enemy trap/status/VFX gameplay, do not add enemy spawn, damage.apply, or encounter completion ports.
- For enemy gameplay only, combat may use kismet.line_trace_single or kismet.sphere_trace_single plus gameplay_statics.apply_damage.
- For reward collection and exit activation, primitive.on_component_begin_overlap is enough to prove the engine activation boundary.
