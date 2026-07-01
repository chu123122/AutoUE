from __future__ import annotations

import json
from pathlib import Path

from core.config import load_llm_profiles
from core.encounter_validation import validate_encounter_spec_data
from core.llm_factory import create_llm
from core.scripted_enemy_cases import SCRIPTED_ENEMY_CASES
from core.validation.registry import validate_node_data


def _invoke(model, schema: str, user: str = "") -> dict:
    response = model.invoke([
        {"role": "system", "content": f"SCHEMA: {schema}\nReturn JSON only."},
        {"role": "user", "content": user},
    ])
    return json.loads(response.content)


def test_scripted_enemy_profiles_emit_valid_selection_and_thin_flow():
    profiles = load_llm_profiles()
    for case, spec in SCRIPTED_ENEMY_CASES.items():
        model = create_llm(f"scripted_enemy_{case}", profiles)
        selection = _invoke(model, "EntityAbilityBehaviorPlanner")
        assert selection == spec.selection
        thin = _invoke(model, "ThinGameplayFlowPlanner")
        validate_node_data("ThinGameplayFlowPlanner", thin)
        assert thin["flows"][0]["entity_id"] == spec.entity_ids[0]


def test_scripted_enemy_profile_emits_non_empty_valid_encounter():
    profiles = load_llm_profiles()
    manifest = {
        "schema_version": "autoue-scene-spawn-manifest/v1",
        "level_name": "Lvl_TestRoom",
        "spawn_groups": [
            {
                "spawn_group": "room_01_guard",
                "source_types": ["EnemySpawnPoint"],
                "point_count": 1,
                "area_count": 0,
                "allowed_enemy_tags": ["ground", "melee", "ranged", "flying", "explosive", "shield"],
                "can_initial_spawn": True,
                "can_runtime_spawn": False,
            }
        ],
        "encounter_zones": [
            {"zone_id": "room_01_entry_zone", "trigger": "on_player_enter_zone", "spawn_group": "room_01_guard", "one_shot": True}
        ],
    }
    for case, spec in SCRIPTED_ENEMY_CASES.items():
        model = create_llm(f"scripted_enemy_{case}", profiles)
        encounter = _invoke(model, "EncounterSpecPlanner", "scene-spawn-manifest.json:\n" + json.dumps(manifest))
        validate_encounter_spec_data(encounter)
        assert encounter["encounters"]
        assert encounter["encounters"][0]["spawn_group"] == "room_01_guard"
        assert encounter["encounters"][0]["composition"][0]["enemy"] == spec.entity_ids[0]


def test_scripted_enemy_profiles_use_mcp_fixture_flag():
    profiles = load_llm_profiles()
    model = create_llm("scripted_enemy_zombie", profiles)
    assert getattr(model, "use_mcp_fixture") is True
    assert getattr(model, "scripted_enemy_case") == "zombie"


def test_projectile_world_adapter_has_spawn_fallback():
    source = (Path("templates/typescript/world_adapter.ts.tmpl")).read_text(encoding="utf-8")

    assert "WorldAdapter.spawnProjectile fallback" in source
    assert "AutoUEFallbackProjectile" in source
