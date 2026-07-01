from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class PrimitiveEntry:
    primitive_id: str
    handler: str | None
    required_runtime_modules: tuple[str, ...]
    engine_ports: tuple[str, ...] = ()
    params_schema: dict[str, dict[str, Any]] | None = None
    default_params: dict[str, Any] | None = None
    supported: bool = True
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "primitive_id": self.primitive_id,
            "handler": self.handler,
            "required_runtime_modules": list(self.required_runtime_modules),
            "engine_ports": list(self.engine_ports),
            "params_schema": dict(self.params_schema or {}),
            "default_params": dict(self.default_params or {}),
            "supported": self.supported,
            "reason": self.reason,
        }


def _primitive(
    primitive_id: str,
    handler: str,
    modules: Iterable[str],
    ports: Iterable[str] = (),
    *,
    schema: dict[str, dict[str, Any]] | None = None,
    defaults: dict[str, Any] | None = None,
    supported: bool = True,
    reason: str = "",
) -> PrimitiveEntry:
    return PrimitiveEntry(
        primitive_id=primitive_id,
        handler=handler,
        required_runtime_modules=tuple(modules),
        engine_ports=tuple(ports),
        params_schema=schema or {},
        default_params=defaults or {},
        supported=supported,
        reason=reason,
    )


PRIMITIVE_RUNTIME_TEMPLATES: dict[str, str] = {
    "player_movement_runtime": "player_movement_runtime",
    "player_combat_runtime": "player_combat_runtime",
    "hit_query_runtime": "hit_query_runtime",
    "damage_runtime": "damage_runtime",
    "pickup_runtime": "pickup_runtime",
    "reward_runtime": "reward_runtime",
    "feedback_runtime": "feedback_runtime",
    # Already-rendered framework/runtime templates.
    "input_harness_runtime": "input_harness_runtime",
    "movement_runtime": "movement_runtime",
    "world_adapter": "world_adapter",
    "entity_registry": "entity_registry",
    "state_blackboard": "state_blackboard",
    "trigger_router": "trigger_router",
    "action_dispatcher": "action_dispatcher",
}


_PRIMITIVES: dict[str, PrimitiveEntry] = {
    "input.read_axis": _primitive(
        "input.read_axis",
        "InputRuntime.readAxis",
        ["input_harness_runtime"],
        ["input.action_binding"],
        defaults={"axis": "horizontal"},
    ),
    "input.read_action": _primitive(
        "input.read_action",
        "InputRuntime.readAction",
        ["input_harness_runtime", "player_combat_runtime"],
        ["input.action_binding"],
        defaults={"action": "attack"},
    ),
    "movement.apply_intent": _primitive(
        "movement.apply_intent",
        "PlayerMovementRuntime.applyIntent",
        ["player_movement_runtime", "movement_runtime"],
        ["pawn.add_movement_input"],
        defaults={"speed": 620, "dash_speed": 1100},
    ),
    "timer.cooldown_gate": _primitive(
        "timer.cooldown_gate",
        "PlayerCombatRuntime.cooldownGate",
        ["player_combat_runtime"],
        defaults={"cooldown": 0.35},
    ),
    "hit.resolve_melee": _primitive(
        "hit.resolve_melee",
        "HitQueryRuntime.resolveMelee",
        ["hit_query_runtime", "world_adapter"],
        ["kismet.sphere_trace_single"],
        defaults={"range": 135, "radius": 70, "target_tags": ["enemy"]},
    ),
    "damage.apply": _primitive(
        "damage.apply",
        "DamageRuntime.apply",
        ["damage_runtime", "world_adapter"],
        ["gameplay_statics.apply_damage"],
        defaults={"amount": 30},
    ),
    "overlap.detect": _primitive(
        "overlap.detect",
        "PickupRuntime.detectOverlap",
        ["pickup_runtime", "trigger_router", "world_adapter"],
        ["primitive.on_component_begin_overlap"],
        defaults={"target": "player"},
    ),
    "timer.once_gate": _primitive(
        "timer.once_gate",
        "PickupRuntime.onceGate",
        ["pickup_runtime"],
    ),
    "reward.grant": _primitive(
        "reward.grant",
        "RewardRuntime.grant",
        ["reward_runtime", "state_blackboard"],
        defaults={"reward_type": "gold", "amount": 1},
    ),
    "feedback.hud_update": _primitive(
        "feedback.hud_update",
        "FeedbackRuntime.hudUpdate",
        ["feedback_runtime", "state_blackboard"],
    ),
    "feedback.set_visibility": _primitive(
        "feedback.set_visibility",
        "FeedbackRuntime.setVisibility",
        ["feedback_runtime", "world_adapter"],
        ["component.set_visibility"],
        defaults={"visible": False},
    ),
    "entity.consume": _primitive(
        "entity.consume",
        "PickupRuntime.consume",
        ["pickup_runtime", "world_adapter"],
        ["actor.destroy"],
        defaults={"mode": "hide_then_destroy"},
    ),
    "state.write": _primitive(
        "state.write",
        "StateBlackboard.write",
        ["state_blackboard"],
        defaults={"scope": "runtime"},
    ),
    "state.read": _primitive(
        "state.read",
        "StateBlackboard.read",
        ["state_blackboard"],
        defaults={"scope": "runtime"},
    ),
}


def get_primitive(primitive_id: str) -> PrimitiveEntry | None:
    return _PRIMITIVES.get(primitive_id)


def all_primitives() -> list[PrimitiveEntry]:
    return [entry for _, entry in sorted(_PRIMITIVES.items())]


def runtime_module_templates() -> dict[str, str]:
    return dict(PRIMITIVE_RUNTIME_TEMPLATES)


def template_for_runtime_module(module_name: str) -> str | None:
    return PRIMITIVE_RUNTIME_TEMPLATES.get(module_name)


def check_primitive_support(primitive_ids: Iterable[str]) -> dict[str, Any]:
    supported: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    required_modules: set[str] = set()
    engine_ports: set[str] = set()
    for primitive_id in primitive_ids:
        entry = get_primitive(primitive_id)
        if entry is None:
            unsupported.append({
                "primitive_id": primitive_id,
                "supported": False,
                "reason": "primitive is not registered",
            })
            continue
        row = entry.to_dict()
        missing_templates = sorted(module for module in entry.required_runtime_modules if template_for_runtime_module(module) is None)
        if not entry.supported:
            unsupported.append({**row, "reason": entry.reason or "primitive runtime is unsupported"})
        elif not entry.handler:
            unsupported.append({**row, "reason": "supported primitive must declare handler"})
        elif not entry.required_runtime_modules:
            unsupported.append({**row, "reason": "supported primitive must declare required_runtime_modules"})
        elif missing_templates:
            unsupported.append({**row, "reason": f"primitive runtime modules have no template mapping: {missing_templates}"})
        else:
            supported.append(row)
            required_modules.update(entry.required_runtime_modules)
            engine_ports.update(entry.engine_ports)
    return {
        "supported_primitives": supported,
        "unsupported_primitives": unsupported,
        "required_runtime_modules": sorted(required_modules),
        "engine_ports": sorted(engine_ports),
    }
