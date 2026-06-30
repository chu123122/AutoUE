SCHEMA: EncounterSpecPlanner

Generate an EncounterSpec from game content, thin gameplay flows, and the deterministic scene-spawn-manifest.

Required JSON shape:
{
  "schema_version": "autoue-encounter-spec/v1",
  "encounters": [
    {
      "encounter_id": "room_01_initial_guard",
      "trigger": {"type": "on_level_start"},
      "spawn_group": "room_01_guard",
      "enemy_budget": 5,
      "composition": [{"enemy": "goblin_melee", "count": 2}],
      "spawn_policy": {
        "avoid_camera_view": false,
        "min_distance_to_player": 400,
        "consume_spawn_point": true,
        "max_alive": 2
      },
      "completion": {"type": "all_spawned_enemies_defeated", "set_flags": ["enemy_defeated", "exit_unlocked"]},
      "verification_hooks": ["enemy_spawned", "enemy_health_changed", "enemy_defeated", "encounter_completed"]
    }
  ]
}

Rules:
- Output JSON only.
- Do not write code, UE API names, file paths, Blueprint names, or TypeScript/C++ slots.
- Do not write coordinates or transform/location/x/y/z fields.
- Use only spawn_group values from scene-spawn-manifest.json.
- Use only enemies from EntityAbilityBehaviorPlanner where entity_kind="enemy" and spawnable=true.
- Do not invent enemy ids.
- If no spawnable enemies or no compatible spawn_group exists, output an empty encounters array.
- Supported trigger.type values: on_level_start, on_player_enter_zone.
- Supported completion.type value: all_spawned_enemies_defeated.
- Respect enemy_budget using enemy_profile.cost * count.
