from __future__ import annotations

import pytest

from core.behavior_recipes import BEHAVIOR_RECIPES, compile_behavior_recipe
from core.content_library import canonicalize_selection
from core.runtime_primitives import get_primitive


def _selection(entity_id: str, capability_ids: list[str], behavior_id: str):
    return canonicalize_selection({
        "selected_entity_ids": [entity_id],
        "selected_capability_ids": capability_ids,
        "selected_behavior_ids": [behavior_id],
    })


def _behavior(entity_behavior: dict, behavior_id: str) -> dict:
    from core.behavior_spec import collect_selected_behaviors, resolve_behavior_capabilities

    row = next(item for item in collect_selected_behaviors(entity_behavior) if item["behavior_id"] == behavior_id)
    row["resolved_capabilities"] = resolve_behavior_capabilities(row)
    return row


def test_player_move_and_attack_recipe_expands_to_connected_primitive_plan():
    behavior = _behavior(_selection("player", ["player.movement.move_actor", "player.attack.apply_damage"], "player.behavior.move_and_attack"), "player.behavior.move_and_attack")
    plan = compile_behavior_recipe(behavior)
    ids = [step["primitive_id"] for step in plan]
    assert ids == [step.primitive_id for step in BEHAVIOR_RECIPES["player.behavior.move_and_attack"]]
    assert {"input.read_axis", "movement.apply_intent", "input.read_action", "timer.cooldown_gate", "hit.resolve_melee", "damage.apply"}.issubset(ids)
    move = next(step for step in plan if step["primitive_id"] == "movement.apply_intent")
    damage = next(step for step in plan if step["primitive_id"] == "damage.apply")
    assert move["params"]["speed"] == 620
    assert damage["params"]["amount"] == 30
    produced = set()
    for step in plan:
        assert get_primitive(step["primitive_id"]), step
        assert all(name in produced or name in {"attack_intent", "move_intent", "attack_allowed", "hit_targets"} for name in step.get("inputs", []))
        produced.update(step.get("outputs", []))


def test_pickup_collect_reward_recipe_resolves_reward_params_from_entity_tags():
    behavior = _behavior(_selection("cell_pickup", ["pickup.collect.grant_reward", "pickup.feedback.spawn_reward_visual"], "pickup.behavior.collect_reward"), "pickup.behavior.collect_reward")
    plan = compile_behavior_recipe(behavior)
    ids = [step["primitive_id"] for step in plan]
    assert ids == [step.primitive_id for step in BEHAVIOR_RECIPES["pickup.behavior.collect_reward"]]
    reward = next(step for step in plan if step["primitive_id"] == "reward.grant")
    visibility = next(step for step in plan if step["primitive_id"] == "feedback.set_visibility")
    assert reward["params"]["reward_type"] == "cell"
    assert reward["params"]["amount"] == 1
    assert visibility["params"]["visible"] is False


def test_recipe_unknown_primitive_fails_loud(monkeypatch):
    from core import behavior_recipes

    monkeypatch.setitem(behavior_recipes.BEHAVIOR_RECIPES, "bad.behavior", (behavior_recipes.RecipeStep("missing.primitive"),))
    with pytest.raises(ValueError, match="unknown primitive"):
        compile_behavior_recipe({"behavior_id": "bad.behavior"})
