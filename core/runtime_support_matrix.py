from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core.content_library import load_dead_cells_library

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
    _entry("gate_lock", "evaluate_unlock", "ActionDispatcher.unlockExit", ["state_blackboard", "action_dispatcher"], []),
    _entry("level_transition", "activate_transition", "ActionDispatcher.openExit", ["world_adapter", "entity_registry", "action_dispatcher"], ["primitive.on_component_begin_overlap", "gameplay_statics.open_level"]),
    _entry("vfx_binding", "spawn_particles", "ActionDispatcher.spawnVfx", ["world_adapter", "entity_registry", "action_dispatcher"], ["component.set_visibility"]),
    _entry("vfx_lifecycle", "tick_or_cleanup", "ActionDispatcher.setVfxVisible", ["world_adapter", "entity_registry", "action_dispatcher"], ["component.set_visibility"]),

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
