from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.content_library import (
    build_candidate_set,
    canonicalize_selection,
    load_dead_cells_library,
    parse_selection_output,
    validate_selection_against_library_and_candidates,
)
from core.validation.common import WorkflowValidationError
from core.workflow_validation import validate_node_output

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "dead_cells_eab_runs"
DOC_ROOT = ROOT / "tests" / "fixtures" / "dead_cells_libraries"


def _walk_text(value) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def test_dead_cells_libraries_are_large_enough_and_exclude_audio():
    lib = load_dead_cells_library()
    assert len(lib["entities"]) >= 50
    assert len(lib["abilities"]) >= 100
    assert len(lib["capabilities"]) >= 100
    assert len(lib["behaviors"]) >= 200
    text = _walk_text({
        "entities": list(lib["entities"].values()),
        "capabilities": list(lib["capabilities"].values()),
        "behaviors": list(lib["behaviors"].values()),
    })
    for forbidden in ("audio", "sound", "sfx", "音效", "声音", "bgm"):
        assert forbidden not in text


@pytest.mark.parametrize(
    ("entity_id", "ability_id", "behavior_id"),
    [
        ("zombie", "zombie.offense", "zombie.offense.resolve_hit"),
        ("health_bar_hud", "health_bar_hud.display", "health_bar_hud.display.refresh_value"),
        ("corpse_dust_vfx", "corpse_dust_vfx.emit", "corpse_dust_vfx.emit.spawn_particles"),
        ("combat_damage_number_hud", "combat_damage_number_hud.display", "combat_damage_number_hud.display.refresh_value"),
        ("side_camera", "side_camera.feedback.impulse", "side_camera.shake_on_trap_trigger"),
    ],
)
def test_entity_capability_behavior_ids_are_cross_linked(entity_id: str, ability_id: str, behavior_id: str):
    lib = load_dead_cells_library()
    capability = lib["capabilities"][ability_id]
    assert capability["entity_id"] == entity_id
    assert capability["capability_id"] == ability_id
    assert capability["semantic_role"] == "capability"
    assert capability["runtime_primitives"]
    assert capability["runtime_features"]
    assert lib["behaviors"][behavior_id]["entity_id"] == entity_id
    assert lib["behaviors"][behavior_id]["ability_id"] == ability_id
    assert lib["behaviors"][behavior_id]["required_capability_ids"]
    assert lib["behaviors"][behavior_id]["runtime_features"]



def test_dead_cells_libraries_forbid_generic_state_or_interaction_ids():
    lib = load_dead_cells_library()
    for collection_name in ('entities', 'capabilities', 'behaviors'):
        for item_id, item in lib[collection_name].items():
            assert not item_id.endswith('.state')
            assert '.interaction' not in item_id
            assert 'accept_interaction' not in item_id
            assert 'resolve_interaction' not in item_id
            if collection_name != 'entities':
                assert 'status' not in item.get('runtime_features', [])
                assert 'interaction' not in item.get('runtime_features', [])
    for behavior in lib['behaviors'].values():
        trigger_text = json.dumps(behavior.get('trigger_model', {}), ensure_ascii=False)
        assert 'state_entity_id' not in trigger_text
        assert 'freeze_status' not in trigger_text

def test_candidate_retrieval_supports_exact_chinese_library_names_and_closure():
    candidate_set = build_candidate_set("玩家使用冰冻手雷冻结奔行者，冰冻特效附着并持续到解冻。")
    assert "runner" in candidate_set["candidate_entity_ids"]
    assert "ice_grenade" in candidate_set["candidate_entity_ids"]
    assert "runner.pursuit" in candidate_set["candidate_capability_ids"]
    assert "runner.pursuit.close_gap" in candidate_set["candidate_behavior_ids"]
    freeze_set = build_candidate_set("玩家走进冰冻陷阱 freeze_trap.freeze_player_on_overlap，冰冻特效和侧视角镜头震动。")
    assert "freeze_trap.sensor.detect_player_overlap" in freeze_set["candidate_capability_ids"]
    assert "side_camera.feedback.impulse" in freeze_set["candidate_capability_ids"]
    assert "freeze_trap.freeze_player_on_overlap" in freeze_set["candidate_behavior_ids"]
    assert "side_camera.shake_on_trap_trigger" in freeze_set["candidate_behavior_ids"]


def test_selection_ids_validate_and_expand_to_canonical_entity_tree():
    candidate_set = build_candidate_set("玩家遭遇僵尸，攻击后出现伤害数字，击败后出口解锁。")
    raw_selection = {
        "selected_entity_ids": ["zombie", "level_exit_door", "combat_damage_number_hud"],
        "selected_capability_ids": [],
        "selected_behavior_ids": [
            "player.combat.attack",
            "zombie.offense.resolve_hit",
            "level_exit_door.lock.evaluate_unlock",
            "combat_damage_number_hud.display.refresh_value",
        ],
    }
    selection = parse_selection_output("EntityAbilityBehaviorPlanner", raw_selection)
    validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", selection, candidate_set)
    canonical = canonicalize_selection(selection)

    entity_ids = {entity["entity_id"] for entity in canonical["entities"]}
    assert {"player", "zombie", "level_exit_door", "combat_damage_number_hud"}.issubset(entity_ids)
    validate_node_output("EntityAbilityBehaviorPlanner", json.dumps(canonical, ensure_ascii=False))


def test_selection_rejects_ids_outside_candidate_set():
    candidate_set = build_candidate_set("玩家遭遇僵尸。")
    selection = parse_selection_output("EntityAbilityBehaviorPlanner", {
        "selected_entity_ids": ["runner"],
        "selected_capability_ids": [],
        "selected_behavior_ids": ["player.combat.attack"],
    })
    with pytest.raises(WorkflowValidationError, match="candidate set"):
        validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", selection, candidate_set)


def test_canonical_validator_rejects_unknown_library_ids():
    bad = {
        "entities": [{
            "entity_id": "not_in_dead_cells_library",
            "display_name": "Unknown",
            "summary": "Unknown entity",
            "abilities": [],
        }],
        "non_goals": [],
    }
    with pytest.raises(WorkflowValidationError, match="dead_cells entity library"):
        validate_node_output("EntityAbilityBehaviorPlanner", json.dumps(bad, ensure_ascii=False))


def test_dead_cells_library_chinese_markdown_docs_exist():
    for filename, heading in [
        ("entities.zh.md", "# 死亡细胞实体库"),
        ("abilities.zh.md", "# 死亡细胞能力库"),
        ("behaviors.zh.md", "# 死亡细胞行为库"),
    ]:
        text = (DOC_ROOT / filename).read_text(encoding="utf-8")
        assert text.startswith(heading)
        assert "不含音效" in text
        assert "player" in text


def test_twenty_entity_ability_behavior_single_node_fixtures_are_valid():
    runs = sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir())
    assert len(runs) == 20
    lib = load_dead_cells_library()
    for run in runs:
        for filename in ("prompt.txt", "candidate_set.json", "selection_raw.json", "entity_behavior.json", "validation.json"):
            assert (run / filename).exists(), f"{run.name} missing {filename}"
        validation = json.loads((run / "validation.json").read_text(encoding="utf-8"))
        assert validation["result"] == "pass", run.name
        selection = json.loads((run / "selection_raw.json").read_text(encoding="utf-8"))
        candidate_set = json.loads((run / "candidate_set.json").read_text(encoding="utf-8"))
        validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", selection, candidate_set)
        canonical = json.loads((run / "entity_behavior.json").read_text(encoding="utf-8"))
        validate_node_output("EntityAbilityBehaviorPlanner", json.dumps(canonical, ensure_ascii=False))
        for entity_id in selection["selected_entity_ids"]:
            assert entity_id in lib["entities"]
        assert "selected_capability_ids" in selection
        assert "selected_ability_ids" not in selection
        for capability_id in selection["selected_capability_ids"]:
            assert capability_id in lib["capabilities"]
        for behavior_id in selection["selected_behavior_ids"]:
            assert behavior_id in lib["behaviors"]
