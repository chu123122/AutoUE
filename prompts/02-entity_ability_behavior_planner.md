SCHEMA: EntityAbilityBehaviorPlanner

This node is a Dead Cells library selector.

It must not create entity, capability, or behavior content. Python injects a retrieved candidate subset from the canonical libraries.

Required JSON output shape:
{
  "selected_entity_ids": ["entity ids that must appear"],
  "selected_capability_ids": ["capability ids from the second library"],
  "selected_behavior_ids": ["behavior ids from the behavior library"]
}

Rules:
- Output JSON only.
- Select IDs only from the candidate set provided at runtime.
- The second library is Capability Library. Do not treat capability as high-level gameplay skill.
- Legacy key selected_ability_ids is forbidden. Use selected_capability_ids only.
- Entity = thing in world/UI/logic.
- Capability = low-level runtime ability/component, no trigger/result.
- Behavior = trigger + required capabilities + effects.
- Interaction belongs in behavior trigger; state is an entity plus lifecycle/effect capabilities and behaviors.
- Do not output entities[], abilities[], behaviors[], summaries, trigger/execution/result text, engine_ports, files, templates, runtime owners, or code fields.
- Include relevant gameplay objects, traps, status, HUD, particles/VFX, camera, exits, pickups, and enemies only when requested or implied.
- Audio/SFX is intentionally excluded.
