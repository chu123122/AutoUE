from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.content_library import load_dead_cells_library
from core.runtime_primitives import check_primitive_support, get_primitive


@dataclass(frozen=True)
class RecipeStep:
    primitive_id: str
    capability_id: str | None = None
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    params: Mapping[str, Any] | None = None


BEHAVIOR_RECIPES: dict[str, tuple[RecipeStep, ...]] = {
    "player.behavior.move_and_attack": (
        RecipeStep("input.read_axis", "player.movement.move_actor", outputs=("move_intent",)),
        RecipeStep("movement.apply_intent", "player.movement.move_actor", inputs=("move_intent",), params={"speed": "$entity.move_speed", "dash_speed": "$entity.dash_speed"}),
        RecipeStep("input.read_action", "player.attack.apply_damage", params={"action": "attack"}, outputs=("attack_intent",)),
        RecipeStep("timer.cooldown_gate", "player.attack.apply_damage", inputs=("attack_intent",), outputs=("attack_allowed",), params={"cooldown": "$entity.attack_cooldown"}),
        RecipeStep("hit.resolve_melee", "player.attack.apply_damage", inputs=("attack_allowed",), outputs=("hit_targets",), params={"range": "$entity.attack_range", "radius": "$entity.hitbox_radius", "target_tags": ["enemy"]}),
        RecipeStep("damage.apply", "player.attack.apply_damage", inputs=("hit_targets",), params={"amount": "$entity.attack_damage"}),
    ),
    "pickup.behavior.collect_reward": (
        RecipeStep("overlap.detect", "pickup.collect.grant_reward", outputs=("pickup_overlap",), params={"target": "player"}),
        RecipeStep("timer.once_gate", "pickup.collect.grant_reward", inputs=("pickup_overlap",), outputs=("pickup_once")),
        RecipeStep("reward.grant", "pickup.collect.grant_reward", inputs=("pickup_once",), outputs=("reward_state"), params={"reward_type": "$entity.reward_type", "amount": "$entity.reward_amount"}),
        RecipeStep("feedback.hud_update", "pickup.feedback.spawn_reward_visual", inputs=("reward_state",)),
        RecipeStep("feedback.set_visibility", "pickup.feedback.spawn_reward_visual", inputs=("reward_state",), params={"visible": False}),
        RecipeStep("entity.consume", "pickup.feedback.spawn_reward_visual", inputs=("reward_state",)),
    ),
}


def has_behavior_recipe(behavior_id: str) -> bool:
    return behavior_id in BEHAVIOR_RECIPES


def behavior_recipe_capability_ids(behavior_id: str) -> set[str]:
    return {step.capability_id for step in BEHAVIOR_RECIPES.get(behavior_id, ()) if step.capability_id}


def _entity_binding(entity: Mapping[str, Any] | None, capability_id: str | None) -> Mapping[str, Any] | None:
    if not capability_id:
        return None
    for binding in (entity or {}).get("capability_bindings", []) if isinstance(entity, Mapping) else []:
        if isinstance(binding, Mapping) and binding.get("capability_id") == capability_id:
            return binding
    return None


def _inferred_entity_params(entity_id: str, entity: Mapping[str, Any] | None) -> dict[str, Any]:
    tags = {str(tag) for tag in (entity or {}).get("content_tags", []) if isinstance(tag, str)}
    params: dict[str, Any] = {}
    if entity_id == "player" or "player" in tags:
        params.update({
            "move_speed": 620,
            "dash_speed": 1100,
            "attack_cooldown": 0.35,
            "attack_range": 135,
            "hitbox_radius": 70,
            "attack_damage": 30,
        })
    if "pickup" in tags or entity_id.endswith("_pickup"):
        reward_type = "gold"
        if "cell" in tags:
            reward_type = "cell"
        elif "healing" in tags or "food" in tags:
            reward_type = "health"
        elif "blueprint" in tags:
            reward_type = "blueprint"
        elif "scroll" in tags:
            reward_type = "stat_scroll"
        params.update({"reward_type": reward_type, "reward_amount": 1})
    return params


def _resolved_capability_params(behavior: Mapping[str, Any], capability_id: str | None) -> dict[str, Any]:
    if not capability_id:
        return {}
    for capability in behavior.get("resolved_capabilities", []) or []:
        if isinstance(capability, Mapping) and capability.get("capability_id") == capability_id and isinstance(capability.get("params"), Mapping):
            return dict(capability["params"])
    return {}


def _literal_or_ref(value: Any, lookup: Mapping[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$entity."):
        key = value.split(".", 1)[1]
        if key not in lookup:
            return None
        return lookup[key]
    if isinstance(value, list):
        return [_literal_or_ref(item, lookup) for item in value]
    if isinstance(value, dict):
        return {key: _literal_or_ref(val, lookup) for key, val in value.items()}
    return value


def _step_params(behavior: Mapping[str, Any], step: RecipeStep) -> dict[str, Any]:
    lib = load_dead_cells_library()
    entity_id = str(behavior.get("bound_entity_id") or behavior.get("entity_id") or behavior.get("primary_entity_id") or "")
    entity = lib["entities"].get(entity_id)
    primitive = get_primitive(step.primitive_id)
    if primitive is None:
        return {}
    capability = lib["capabilities"].get(step.capability_id or "")
    binding = _entity_binding(entity, step.capability_id)
    overrides = behavior.get("capability_overrides", {}) if isinstance(behavior.get("capability_overrides", {}), Mapping) else {}
    override = overrides.get(step.capability_id or "")

    params: dict[str, Any] = dict(primitive.default_params or {})
    if isinstance(capability, Mapping):
        params.update(dict(capability.get("default_params") or {}))
    if isinstance(entity, Mapping):
        params.update(dict(entity.get("runtime") or {}))
    params.update(_inferred_entity_params(entity_id, entity))
    if binding and isinstance(binding.get("params"), Mapping):
        params.update(dict(binding["params"]))
    params.update(_resolved_capability_params(behavior, step.capability_id))
    if isinstance(override, Mapping):
        params.update(dict(override))

    lookup = dict(params)
    for key, value in dict(step.params or {}).items():
        resolved = _literal_or_ref(value, lookup)
        if resolved is not None:
            params[key] = resolved
    params.setdefault("bound_entity_id", entity_id)
    params.setdefault("entity_id", entity_id)
    return params


def _validate_required_params(label: str, schema: Mapping[str, Any], params: Mapping[str, Any]) -> None:
    for key, rule in schema.items():
        if isinstance(rule, Mapping) and rule.get("required") and key not in params:
            raise ValueError(f"BehaviorRecipeCompiler: {label} missing required param {key}")


def compile_behavior_recipe(behavior: Mapping[str, Any]) -> list[dict[str, Any]]:
    behavior_id = str(behavior.get("behavior_id") or "")
    plan: list[dict[str, Any]] = []
    for step in BEHAVIOR_RECIPES.get(behavior_id, ()):
        primitive = get_primitive(step.primitive_id)
        if primitive is None:
            raise ValueError(f"BehaviorRecipeCompiler: unknown primitive {step.primitive_id} for {behavior_id}")
        params = _step_params(behavior, step)
        _validate_required_params(f"{behavior_id}:{step.primitive_id}", primitive.params_schema or {}, params)
        plan.append({
            "primitive_id": step.primitive_id,
            "capability_id": step.capability_id,
            "handler": primitive.handler,
            "params": params,
            "inputs": list(step.inputs),
            "outputs": list(step.outputs),
            "required_runtime_modules": list(primitive.required_runtime_modules),
            "engine_ports": list(primitive.engine_ports),
        })
    return plan


def primitive_support_summary(primitive_plan: list[Mapping[str, Any]]) -> dict[str, Any]:
    primitive_ids = [str(step.get("primitive_id") or "") for step in primitive_plan if isinstance(step, Mapping) and step.get("primitive_id")]
    return check_primitive_support(primitive_ids)
