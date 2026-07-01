from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core.content_library import load_dead_cells_library

CANONICAL_ENEMY_CAPABILITY_IDS = {
    "enemy.spawn.spawn_actor",
    "enemy.sensor.detect_player_by_distance",
    "enemy.movement.chase_target",
    "enemy.movement.keep_distance",
    "enemy.movement.patrol_between_points",
    "enemy.movement.teleport_to_target",
    "enemy.attack.melee_hitbox",
    "enemy.attack.projectile_spawn",
    "enemy.attack.self_destruct",
    "enemy.attack.area_burst",
    "enemy.defense.directional_block",
    "enemy.defense.invulnerable_window",
    "enemy.health.receive_damage",
    "enemy.death.emit_death_event",
    "enemy.reward.drop_on_death",
    "encounter.complete.complete_when_all_dead",
}

ENEMY_RUNTIME_CAPABILITY_KINDS = {
    "enemy_spawn",
    "enemy_sensor",
    "enemy_movement",
    "enemy_attack",
    "enemy_defense",
    "enemy_health",
    "enemy_death",
    "enemy_reward",
    "encounter",
}

SUPPORTED_ACTION_TYPES = {
    "write_state",
    "clear_state",
    "movement_gate",
    "set_vfx_visible",
    "camera_impulse",
    "set_hud_value",
    "unlock_exit",
    "open_exit",
    "spawn_vfx",
    "destroy_entity",
    "apply_damage",
    "start_timer",
    "enemy_spawn_actor",
    "enemy_detect_player",
    "enemy_chase_target",
    "enemy_keep_distance",
    "enemy_melee_attack",
    "enemy_projectile_attack",
    "enemy_self_destruct",
    "enemy_directional_block",
    "enemy_receive_damage",
    "enemy_emit_death_event",
    "encounter_complete_when_all_dead",
}

FRAMEWORK_RUNTIME_MODULES = [
    "world_adapter",
    "entity_registry",
    "state_blackboard",
    "trigger_router",
    "condition_checker",
    "action_dispatcher",
    "behavior_orchestrator",
]


@dataclass(frozen=True)
class SupportEntry:
    capability_kind: str
    action_kind: str
    handler: str | None
    required_runtime_modules: tuple[str, ...]
    engine_ports: tuple[str, ...]
    supported: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_kind": self.capability_kind,
            "action_kind": self.action_kind,
            "handler": self.handler,
            "required_runtime_modules": list(self.required_runtime_modules),
            "engine_ports": list(self.engine_ports),
            "supported": self.supported,
            "reason": self.reason,
        }


class CapabilitySupportMatrix:
    def __init__(self, entries: Iterable[SupportEntry]):
        self._entries = {(entry.capability_kind, entry.action_kind): entry for entry in entries}

    def lookup(self, capability_kind: str, action_kind: str) -> SupportEntry | None:
        return self._entries.get((capability_kind, action_kind))

    def require(self, capability: dict[str, Any]) -> SupportEntry:
        kind = str(capability.get("capability_kind") or "")
        action = str(capability.get("action_kind") or "")
        entry = self.lookup(kind, action)
        if entry is None:
            raise KeyError(f"missing support matrix entry for capability_kind={kind!r} action_kind={action!r}")
        return entry

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "autoue-capability-support-matrix/v1",
            "entries": [entry.to_dict() for entry in sorted(self._entries.values(), key=lambda x: (x.capability_kind, x.action_kind))],
        }


def _entry(kind: str, action: str, handler: str | None, modules: list[str], ports: list[str] | None = None, *, supported: bool = True, reason: str = "") -> SupportEntry:
    return SupportEntry(kind, action, handler, tuple(modules), tuple(ports or []), supported, reason)


DEFAULT_SUPPORT_MATRIX = CapabilitySupportMatrix([
    _entry("sensor_overlap", "detect_overlap", "TriggerRouter.bindOverlapEnter", ["world_adapter", "entity_registry", "trigger_router"], ["primitive.on_component_begin_overlap"]),
    _entry("apply_effect", "apply_freeze", "ActionDispatcher.writeState", ["state_blackboard", "action_dispatcher"], []),
    _entry("movement_gate", "block_by_state", "ActionDispatcher.movementGate", ["state_blackboard", "action_dispatcher", "movement_runtime"], []),
    _entry("vfx_binding", "set_visible_while_state", "ActionDispatcher.setVfxVisible", ["world_adapter", "entity_registry", "state_blackboard", "action_dispatcher"], ["component.set_visibility"]),
    _entry("camera_feedback", "camera_impulse", "ActionDispatcher.cameraImpulse", ["world_adapter", "action_dispatcher"], ["camera.update_view_target"]),
    _entry("hud_binding", "refresh_value", "ActionDispatcher.setHudValue", ["world_adapter", "entity_registry", "state_blackboard", "action_dispatcher"], ["widget.set_text", "widget.set_percent"]),
    _entry("hud_feedback", "flash_warning", "ActionDispatcher.setHudValue", ["world_adapter", "entity_registry", "state_blackboard", "action_dispatcher"], ["widget.set_render_opacity"]),
    _entry("hud_binding", "set_percent", None, [], ["widget.set_percent"], supported=False, reason="dedicated HUD set_percent runtime handler is not implemented"),
    _entry("hud_feedback", "set_opacity", None, [], ["widget.set_render_opacity"], supported=False, reason="dedicated HUD opacity runtime handler is not implemented"),
    _entry("gate_lock", "evaluate_unlock", "ActionDispatcher.unlockExit", ["state_blackboard", "action_dispatcher"], []),
    _entry("level_transition", "activate_transition", "ActionDispatcher.openExit", ["world_adapter", "entity_registry", "action_dispatcher"], ["primitive.on_component_begin_overlap", "gameplay_statics.open_level"]),
    _entry("vfx_binding", "spawn_particles", "ActionDispatcher.spawnVfx", ["world_adapter", "entity_registry", "action_dispatcher"], ["component.set_visibility"]),
    _entry("vfx_lifecycle", "tick_or_cleanup", "ActionDispatcher.setVfxVisible", ["world_adapter", "entity_registry", "action_dispatcher"], ["component.set_visibility"]),
    _entry("vfx_lifecycle", "cleanup_after_duration", None, [], ["component.set_visibility"], supported=False, reason="VFX cleanup-after-duration runtime handler is not implemented"),
    _entry("vfx_lifecycle", "attach_to_target", None, [], ["component.attach_to_component"], supported=False, reason="VFX attach runtime handler is not implemented"),
    _entry("enemy_spawn", "spawn_actor", "EnemySpawnRuntime.spawnEnemy", ["enemy_runtime", "enemy_spawn_runtime", "enemy_registry", "world_adapter"], ["actor.spawn"]),
    _entry("enemy_sensor", "detect_player_by_distance", "EnemyPerception.detectPlayer", ["enemy_runtime", "enemy_perception", "enemy_registry", "world_adapter"], ["actor.get_distance_to"]),
    _entry("enemy_movement", "chase_target", "EnemyMovement.chaseTarget", ["enemy_runtime", "enemy_movement", "enemy_registry", "world_adapter"], ["actor.get_distance_to", "actor.set_actor_location"]),
    _entry("enemy_movement", "keep_distance", "EnemyMovement.keepDistance", ["enemy_runtime", "enemy_movement", "enemy_registry", "world_adapter"], ["actor.get_distance_to", "actor.set_actor_location"]),
    _entry("enemy_movement", "patrol_between_points", None, [], ["actor.set_actor_location"], supported=False, reason="enemy patrol runtime handler is not implemented"),
    _entry("enemy_movement", "teleport_to_target", None, [], ["actor.set_actor_location"], supported=False, reason="enemy teleport runtime handler is not implemented"),
    _entry("enemy_attack", "melee_hitbox", "EnemyCombat.resolveMeleeHit", ["enemy_runtime", "enemy_combat", "enemy_presentation", "enemy_registry", "world_adapter"], ["kismet.sphere_trace_single", "gameplay_statics.apply_damage"]),
    _entry("enemy_attack", "projectile_spawn", "EnemyCombat.spawnProjectile", ["enemy_runtime", "enemy_combat", "enemy_presentation", "enemy_projectile_runtime", "world_adapter"], ["projectile.spawn"]),
    _entry("enemy_attack", "self_destruct", "EnemyCombat.selfDestruct", ["enemy_runtime", "enemy_combat", "enemy_presentation", "enemy_health", "enemy_death_events", "world_adapter"], ["gameplay_statics.apply_damage", "actor.destroy"]),
    _entry("enemy_attack", "area_burst", None, [], ["gameplay_statics.apply_damage"], supported=False, reason="enemy area burst runtime handler is not implemented"),
    _entry("enemy_defense", "directional_block", "EnemyCombat.resolveDirectionalBlock", ["enemy_runtime", "enemy_combat", "enemy_presentation", "enemy_health"], ["actor.get_forward_vector"]),
    _entry("enemy_defense", "invulnerable_window", None, [], [], supported=False, reason="enemy invulnerable window runtime handler is not implemented"),
    _entry("enemy_health", "receive_damage", "EnemyHealth.applyDamage", ["enemy_runtime", "enemy_health", "enemy_presentation", "enemy_registry", "world_adapter"], ["gameplay_statics.apply_damage", "actor.on_take_any_damage"]),
    _entry("enemy_death", "emit_death_event", "EnemyDeathEvents.emitDeath", ["enemy_runtime", "enemy_death_events", "enemy_presentation", "enemy_registry", "encounter_manager"], ["actor.on_destroyed"]),
    _entry("enemy_reward", "drop_on_death", None, [], [], supported=False, reason="enemy reward drop runtime handler is not implemented"),
    _entry("encounter", "complete_when_all_dead", "EncounterManager.completeWhenAllDead", ["enemy_runtime", "encounter_manager", "enemy_registry"], ["encounter.alive_count"]),

    _entry("movement", "move_actor", None, [], ["input.action_binding", "pawn.add_movement_input"], supported=False, reason="general movement runtime is not implemented by behavior framework support matrix"),
    _entry("combat", "apply_damage", None, [], ["input.action_binding", "gameplay_statics.apply_damage"], supported=False, reason="combat damage runtime is not implemented"),
    _entry("enemy_combat", "enemy_attack", None, [], ["kismet.sphere_trace_single", "gameplay_statics.apply_damage"], supported=False, reason="enemy encounter/combat runtime is optional and not implemented by the generic behavior framework"),
    _entry("enemy_pursuit", "chase_target", None, [], ["actor.get_distance_to", "pawn.add_movement_input"], supported=False, reason="enemy encounter movement runtime is optional and not implemented by the generic behavior framework"),
    _entry("hazard_arming", "arm_hazard", None, [], ["primitive.on_component_begin_overlap"], supported=False, reason="hazard arming window runtime is not implemented"),
    _entry("hazard_resolution", "apply_hazard_damage", None, [], ["primitive.on_component_begin_overlap", "gameplay_statics.apply_damage"], supported=False, reason="hazard damage runtime is not implemented"),
    _entry("apply_effect", "apply_poison_dot", None, [], ["primitive.on_component_begin_overlap"], supported=False, reason="poison periodic damage handler is not implemented"),
    _entry("apply_effect", "apply_burn", None, [], ["primitive.on_component_begin_overlap"], supported=False, reason="burn effect handler is not implemented"),
    _entry("chest_reward", "open_reward", None, [], [], supported=False, reason="reward/inventory runtime is not implemented"),
    _entry("curse_counter", "add_curse_counter", None, [], [], supported=False, reason="curse counter HUD/runtime is not implemented"),
    _entry("pickup_collection", "grant_reward", None, [], ["primitive.on_component_begin_overlap"], supported=False, reason="pickup inventory/currency runtime is not implemented"),
    _entry("reward_feedback", "spawn_reward_visual", None, [], ["component.set_visibility"], supported=False, reason="reward feedback runtime is not implemented"),
    _entry("teleport_transition", "activate_transition", None, [], ["primitive.on_component_begin_overlap", "gameplay_statics.open_level"], supported=False, reason="teleport transition runtime is not implemented"),
    _entry("transaction", "purchase_item", None, [], [], supported=False, reason="inventory/currency transaction runtime is not implemented"),
    _entry("upgrade", "apply_item_upgrade", None, [], [], supported=False, reason="equipment upgrade runtime is not implemented"),
    _entry("weapon_effect", "apply_bleed_on_hit", None, [], ["gameplay_statics.apply_damage"], supported=False, reason="bleed weapon effect runtime is not implemented"),
    _entry("chain_lightning", "apply_shock_chain", None, [], ["kismet.sphere_trace_single", "component.set_visibility"], supported=False, reason="chain lightning runtime is not implemented"),
    _entry("platform_state", "collapse_when_touched", None, [], ["primitive.on_component_begin_overlap"], supported=False, reason="platform collapse runtime is not implemented"),
    _entry("generic_capability", "state_write", None, [], [], supported=False, reason="generic capability has no concrete runtime handler"),
])


def check_capability_support(capability_ids: Iterable[str], matrix: CapabilitySupportMatrix | None = None) -> dict[str, Any]:
    lib = load_dead_cells_library()
    matrix = matrix or DEFAULT_SUPPORT_MATRIX
    unsupported: list[dict[str, Any]] = []
    supported_rows: list[dict[str, Any]] = []
    required_modules: set[str] = set(FRAMEWORK_RUNTIME_MODULES)
    engine_ports: set[str] = set()

    for capability_id in capability_ids:
        capability = lib["capabilities"].get(capability_id)
        if capability is None:
            unsupported.append({
                "capability_id": capability_id,
                "supported": False,
                "reason": "selected capability is not in Capability Library",
                "missing_matrix_entry": False,
            })
            continue
        kind = str(capability.get("capability_kind") or "")
        action = str(capability.get("action_kind") or "")
        if kind in ENEMY_RUNTIME_CAPABILITY_KINDS and capability_id not in CANONICAL_ENEMY_CAPABILITY_IDS:
            unsupported.append({
                "capability_id": capability_id,
                "capability_kind": kind,
                "action_kind": action,
                "supported": False,
                "reason": "entity-specific enemy capability is legacy unsupported; runtime must consume canonical capability prototypes via resolved_capabilities",
                "missing_matrix_entry": False,
            })
            continue
        entry = matrix.lookup(kind, action)
        if entry is None:
            unsupported.append({
                "capability_id": capability_id,
                "capability_kind": kind,
                "action_kind": action,
                "supported": False,
                "reason": f"missing support matrix entry for capability_kind={kind} action_kind={action}",
                "missing_matrix_entry": True,
            })
            continue
        row = entry.to_dict()
        row.update({"capability_id": capability_id})
        if entry.supported:
            required_modules.update(entry.required_runtime_modules)
            engine_ports.update(entry.engine_ports)
            supported_rows.append(row)
        else:
            unsupported.append({**row, "reason": entry.reason or "capability runtime is unsupported"})

    return {
        "schema_version": "autoue-runtime-support-check/v1",
        "status": "unsupported" if unsupported else "supported",
        "required_runtime_modules": sorted(required_modules),
        "engine_ports": sorted(engine_ports),
        "supported_capabilities": supported_rows,
        "unsupported_capabilities": unsupported,
    }
