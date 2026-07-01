from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MELEE_CAPABILITIES = [
    "enemy.spawn.spawn_actor",
    "enemy.sensor.detect_player_by_distance",
    "enemy.movement.chase_target",
    "enemy.attack.melee_hitbox",
    "enemy.health.receive_damage",
    "enemy.death.emit_death_event",
    "encounter.complete.complete_when_all_dead",
]
PROJECTILE_CAPABILITIES = [
    "enemy.spawn.spawn_actor",
    "enemy.sensor.detect_player_by_distance",
    "enemy.movement.keep_distance",
    "enemy.attack.projectile_spawn",
    "enemy.health.receive_damage",
    "enemy.death.emit_death_event",
    "encounter.complete.complete_when_all_dead",
]
SELF_DESTRUCT_CAPABILITIES = [
    "enemy.spawn.spawn_actor",
    "enemy.sensor.detect_player_by_distance",
    "enemy.movement.chase_target",
    "enemy.attack.self_destruct",
    "enemy.health.receive_damage",
    "enemy.death.emit_death_event",
    "encounter.complete.complete_when_all_dead",
]
SHIELD_CAPABILITIES = [
    "enemy.spawn.spawn_actor",
    "enemy.sensor.detect_player_by_distance",
    "enemy.movement.chase_target",
    "enemy.defense.directional_block",
    "enemy.attack.melee_hitbox",
    "enemy.health.receive_damage",
    "enemy.death.emit_death_event",
    "encounter.complete.complete_when_all_dead",
]

ENGINE_PORTS_BY_ACTION = {
    "enemy_spawn_actor": ["actor.spawn"],
    "enemy_detect_player": ["actor.get_distance_to"],
    "enemy_chase_target": ["actor.set_actor_location"],
    "enemy_keep_distance": ["actor.set_actor_location"],
    "enemy_melee_attack": ["kismet.sphere_trace_single", "gameplay_statics.apply_damage"],
    "enemy_projectile_attack": ["projectile.spawn"],
    "enemy_self_destruct": ["gameplay_statics.apply_damage", "actor.destroy"],
    "enemy_directional_block": ["actor.get_forward_vector"],
    "enemy_receive_damage": ["actor.on_take_any_damage"],
    "enemy_emit_death_event": ["actor.on_destroyed"],
    "encounter_complete_when_all_dead": ["encounter.alive_count"],
}

CAPABILITY_TO_ACTION = {
    "enemy.spawn.spawn_actor": "enemy_spawn_actor",
    "enemy.sensor.detect_player_by_distance": "enemy_detect_player",
    "enemy.movement.chase_target": "enemy_chase_target",
    "enemy.movement.keep_distance": "enemy_keep_distance",
    "enemy.attack.melee_hitbox": "enemy_melee_attack",
    "enemy.attack.projectile_spawn": "enemy_projectile_attack",
    "enemy.attack.self_destruct": "enemy_self_destruct",
    "enemy.defense.directional_block": "enemy_directional_block",
    "enemy.health.receive_damage": "enemy_receive_damage",
    "enemy.death.emit_death_event": "enemy_emit_death_event",
    "encounter.complete.complete_when_all_dead": "encounter_complete_when_all_dead",
}


@dataclass(frozen=True)
class ScriptedEnemyCase:
    case: str
    fixture_name: str
    prompt: str
    entity_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    behavior_ids: tuple[str, ...]
    expected_attack_type: str

    @property
    def selection(self) -> dict[str, list[str]]:
        return {
            "selected_entity_ids": list(self.entity_ids),
            "selected_capability_ids": list(self.capability_ids),
            "selected_behavior_ids": list(self.behavior_ids),
        }


SCRIPTED_ENEMY_CASES: dict[str, ScriptedEnemyCase] = {
    "zombie": ScriptedEnemyCase(
        case="zombie",
        fixture_name="01-zombie_melee",
        prompt="僵尸近战 canonical prototype runtime",
        entity_ids=("zombie",),
        capability_ids=tuple(MELEE_CAPABILITIES),
        behavior_ids=("enemy.behavior.chase_and_melee",),
        expected_attack_type="melee_hitbox",
    ),
    "archer": ScriptedEnemyCase(
        case="archer",
        fixture_name="02-archer_projectile",
        prompt="弓箭手远程 canonical prototype runtime",
        entity_ids=("archer",),
        capability_ids=tuple(PROJECTILE_CAPABILITIES),
        behavior_ids=("enemy.behavior.keep_distance_and_projectile",),
        expected_attack_type="projectile_spawn",
    ),
    "kamikaze": ScriptedEnemyCase(
        case="kamikaze",
        fixture_name="03-kamikaze_self_destruct",
        prompt="自爆蝙蝠 canonical prototype runtime",
        entity_ids=("kamikaze_bat",),
        capability_ids=tuple(SELF_DESTRUCT_CAPABILITIES),
        behavior_ids=("enemy.behavior.chase_and_self_destruct",),
        expected_attack_type="self_destruct",
    ),
    "shield": ScriptedEnemyCase(
        case="shield",
        fixture_name="04-shield_bearer_block",
        prompt="持盾兵 canonical prototype runtime",
        entity_ids=("shield_bearer",),
        capability_ids=tuple(SHIELD_CAPABILITIES),
        behavior_ids=("enemy.behavior.block_then_counter",),
        expected_attack_type="melee_hitbox",
    ),
}


def get_scripted_enemy_case(case: str) -> ScriptedEnemyCase:
    try:
        return SCRIPTED_ENEMY_CASES[case]
    except KeyError as exc:
        raise ValueError(f"unknown scripted enemy case: {case}") from exc


def candidate_query_for_case(case: str) -> str:
    spec = get_scripted_enemy_case(case)
    return " ".join([spec.prompt, *spec.entity_ids, *spec.capability_ids, *spec.behavior_ids])


def thin_flow_for_case(case: str) -> dict[str, Any]:
    spec = get_scripted_enemy_case(case)
    flows = []
    for entity_id in spec.entity_ids:
        for behavior_id in spec.behavior_ids:
            stages = []
            for capability_id in spec.capability_ids:
                action = CAPABILITY_TO_ACTION.get(capability_id)
                ports = ENGINE_PORTS_BY_ACTION.get(action or "", [])
                if not action or not ports:
                    continue
                stages.append(
                    {
                        "stage": "Ability/Action",
                        "contract": f"{action} for {behavior_id}",
                        "inputs": ["BehaviorSpec", "runtime_params"],
                        "outputs": [action],
                        "engine_ports": ports,
                    }
                )
            flows.append(
                {
                    "flow_id": f"flow_{behavior_id.replace('.', '_')}",
                    "entity_id": entity_id,
                    "source_behavior_id": behavior_id,
                    "stages": stages,
                    "verification": [
                        "EnemySpawnedByEncounter",
                        "EnemyAttackTelegraph",
                        "EnemyAttackActive",
                        f"EnemyAttackResolved type={spec.expected_attack_type}",
                        "EncounterCompleted=1",
                    ],
                }
            )
    return {"flows": flows}


def encounter_for_case(case: str, spawn_group: str) -> dict[str, Any]:
    spec = get_scripted_enemy_case(case)
    budget_by_case = {"zombie": 1, "archer": 2, "kamikaze": 3, "shield": 2}
    budget = max(budget_by_case.get(case, 1), len(spec.entity_ids))
    return {
        "schema_version": "autoue-encounter-spec/v1",
        "encounters": [
            {
                "encounter_id": f"room_01_{case}_encounter",
                "trigger": {"type": "on_level_start"},
                "spawn_group": spawn_group,
                "enemy_budget": budget,
                "composition": [{"enemy": entity_id, "count": 1} for entity_id in spec.entity_ids],
                "spawn_policy": {
                    "avoid_camera_view": False,
                    "min_distance_to_player": 400,
                    "consume_spawn_point": True,
                    "max_alive": max(1, len(spec.entity_ids)),
                },
                "completion": {
                    "type": "all_spawned_enemies_defeated",
                    "set_flags": ["enemy_defeated", "exit_unlocked"],
                },
                "verification_hooks": [
                    "EnemySpawnedByEncounter",
                    "EnemyAttackTelegraph",
                    "EnemyAttackActive",
                    "EnemyAttackResolved",
                    "EncounterCompleted=1",
                ],
            }
        ],
    }
