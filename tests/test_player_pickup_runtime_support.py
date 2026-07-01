from __future__ import annotations

from core.behavior_spec import compile_and_check
from core.content_library import canonicalize_selection

PLAYER_PICKUP_CAPS = [
    "player.movement.move_actor",
    "player.attack.apply_damage",
    "pickup.collect.grant_reward",
    "pickup.feedback.spawn_reward_visual",
]


def _player_pickup_selection():
    return canonicalize_selection({
        "selected_entity_ids": ["player", "gold_pickup"],
        "selected_capability_ids": PLAYER_PICKUP_CAPS,
        "selected_behavior_ids": ["player.behavior.move_and_attack", "pickup.behavior.collect_reward"],
    })


def test_player_pickup_behavior_spec_has_primitive_plan_and_v2_support_gate():
    spec, support = compile_and_check(_player_pickup_selection())
    assert support["schema_version"] == "autoue-runtime-support-check/v2"
    assert support["status"] == "supported"
    assert support["static_support"] == "supported"
    assert support["runtime_proof"] == "not_run"
    assert support["unsupported_capabilities"] == []
    assert support["unsupported_primitives"] == []
    for capability_id in PLAYER_PICKUP_CAPS:
        assert capability_id in support["behavior_by_capability"]

    behaviors = {item["behavior_id"]: item for item in spec["behaviors"]}
    player_plan = behaviors["player.behavior.move_and_attack"]["primitive_plan"]
    pickup_plan = behaviors["pickup.behavior.collect_reward"]["primitive_plan"]
    assert player_plan and pickup_plan
    for step in player_plan + pickup_plan:
        assert step["handler"]
        assert step["required_runtime_modules"]
    assert "player_movement_runtime" in support["required_runtime_modules"]
    assert "pickup_runtime" in support["required_runtime_modules"]
    assert "reward_runtime" in support["required_runtime_modules"]
    assert "feedback_runtime" in support["required_runtime_modules"]


def test_player_pickup_capabilities_are_not_blocked_by_missing_support_matrix_handlers():
    _, support = compile_and_check(_player_pickup_selection())
    unsupported_ids = {item.get("capability_id") for item in support["unsupported_capabilities"]}
    assert not (set(PLAYER_PICKUP_CAPS) & unsupported_ids)
    supported_ids = {item.get("capability_id") for item in support["supported_capabilities"]}
    assert set(PLAYER_PICKUP_CAPS).issubset(supported_ids)
