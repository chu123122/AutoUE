from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.BaseLLMNode import GraphState
from core.content_library import build_candidate_set, canonicalize_selection, load_dead_cells_library, parse_selection_output, validate_selection_against_library_and_candidates
from core.validation.common import WorkflowValidationError
from core.workflow_validation import validate_node_output

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "dead_cells_eab_runs"
DOC_ROOT = ROOT / "tests" / "fixtures" / "dead_cells_libraries"
ENEMY_RUNTIME_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "dead_cells_enemy_runtime_cases"
ENEMY_CHASE_MELEE = ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.chase_target", "enemy.attack.melee_hitbox", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"]
ARCHER_PROJECTILE = ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.keep_distance", "enemy.attack.projectile_spawn", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"]
KAMIKAZE = ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.chase_target", "enemy.attack.self_destruct", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"]
SHIELD = ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.chase_target", "enemy.defense.directional_block", "enemy.attack.melee_hitbox", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"]


def test_dead_cells_libraries_are_canonical_and_exclude_audio():
    lib = load_dead_cells_library()
    assert len(lib["entities"]) >= 50
    assert len(lib["capabilities"]) >= 30
    assert len(lib["behaviors"]) >= 10
    text = json.dumps({"entities": list(lib["entities"].values()), "capabilities": list(lib["capabilities"].values()), "behaviors": list(lib["behaviors"].values())}, ensure_ascii=False).lower()
    for forbidden in ("audio", "sound", "sfx", "音效", "声音", "bgm"):
        assert forbidden not in text
    for legacy in ("zombie.offense", "archer.offense", "runner.pursuit", '"ability_id"'):
        assert legacy not in text


@pytest.mark.parametrize(("capability_id", "kind", "action"), [
    ("enemy.attack.melee_hitbox", "enemy_attack", "melee_hitbox"),
    ("enemy.attack.projectile_spawn", "enemy_attack", "projectile_spawn"),
    ("enemy.movement.chase_target", "enemy_movement", "chase_target"),
    ("hud.display.refresh_value", "hud_binding", "refresh_value"),
    ("vfx.spawn.spawn_particles", "vfx_binding", "spawn_particles"),
    ("pickup.collect.grant_reward", "pickup_collection", "grant_reward"),
])
def test_capability_prototypes_are_cross_linked(capability_id: str, kind: str, action: str):
    lib = load_dead_cells_library()
    cap = lib["capabilities"][capability_id]
    assert cap["semantic_role"] == "capability"
    assert cap["capability_scope"] == "canonical_prototype"
    assert cap["capability_kind"] == kind
    assert cap["action_kind"] == action
    assert isinstance(cap["params_schema"], dict)
    assert isinstance(cap["runtime_features"], list) and cap["runtime_features"]
    assert any(capability_id in b["required_capability_ids"] for b in lib["behaviors"].values()) or capability_id in {"enemy.movement.patrol_between_points", "enemy.movement.teleport_to_target", "enemy.attack.area_burst", "enemy.defense.invulnerable_window", "enemy.reward.drop_on_death", "hud.display.set_percent", "hud.feedback.set_opacity", "vfx.lifecycle.cleanup_after_duration", "vfx.lifecycle.attach_to_target"}


def test_empty_params_schema_is_only_used_for_parameterless_bindings():
    lib = load_dead_cells_library()
    bindings_by_capability: dict[str, list[dict]] = {}
    for entity in lib["entities"].values():
        for binding in entity.get("capability_bindings", []) or []:
            bindings_by_capability.setdefault(binding["capability_id"], []).append(binding)

    for capability_id, capability in lib["capabilities"].items():
        schema = capability["params_schema"]
        assert isinstance(schema, dict), capability_id
        for binding in bindings_by_capability.get(capability_id, []):
            params = binding.get("params", {})
            defaults = capability.get("default_params", {})
            unknown = set(params) - set(schema) - set(defaults)
            assert not unknown, f"{binding} has params not declared by {capability_id}.params_schema/default_params"
            if not schema:
                assert not params, f"{capability_id} uses empty params_schema but {binding} supplies params"


def test_enemy_entities_bind_canonical_capabilities_and_support_matrix_is_precise():
    from core.runtime_support_matrix import check_capability_support

    lib = load_dead_cells_library()
    cases = {
        "zombie": ("enemy.behavior.chase_and_melee", set(ENEMY_CHASE_MELEE)),
        "archer": ("enemy.behavior.keep_distance_and_projectile", set(ARCHER_PROJECTILE)),
        "kamikaze_bat": ("enemy.behavior.chase_and_self_destruct", set(KAMIKAZE)),
        "shield_bearer": ("enemy.behavior.block_then_counter", set(SHIELD)),
    }
    for entity_id, (behavior_id, required) in cases.items():
        bound = {b["capability_id"]: b["params"] for b in lib["entities"][entity_id]["capability_bindings"]}
        assert required.issubset(bound)
        support = check_capability_support(required)
        assert support["status"] == "supported"
        assert {"enemy_registry", "enemy_death_events", "encounter_manager"}.issubset(support["required_runtime_modules"])
        assert set(lib["behaviors"][behavior_id]["required_capability_ids"]) == required
    unsupported = check_capability_support(["enemy.movement.teleport_to_target", "hazard.arming.arm_hazard"])
    assert unsupported["status"] == "unsupported"


def test_legacy_ids_are_rejected_at_selection_boundary():
    with pytest.raises(WorkflowValidationError, match="selected_ability_ids"):
        parse_selection_output("EntityAbilityBehaviorPlanner", {"selected_ability_ids": ["zombie.offense"], "selected_behavior_ids": []})
    with pytest.raises(WorkflowValidationError, match="legacy ID"):
        parse_selection_output("EntityAbilityBehaviorPlanner", {"selected_capability_ids": ["zombie.offense"], "selected_behavior_ids": []})


def test_candidate_retrieval_uses_prototypes_and_binding_summary():
    cs = build_candidate_set("玩家遭遇僵尸，击败后出口解锁，HUD 刷新。")
    assert "zombie" in cs["candidate_entity_ids"]
    assert "enemy.attack.melee_hitbox" in cs["candidate_capability_ids"]
    assert "enemy.behavior.chase_and_melee" in cs["candidate_behavior_ids"]
    assert cs["candidate_capability_prototypes"]
    summary = {row["entity_id"]: row["capability_ids"] for row in cs["entity_capability_bindings_summary"]}
    assert "enemy.attack.melee_hitbox" in summary["zombie"]


def test_selection_requires_capability_coverage_and_expands_to_canonical_tree():
    cs = build_candidate_set("玩家遭遇僵尸。")
    bad = parse_selection_output("EntityAbilityBehaviorPlanner", {"selected_entity_ids": ["zombie"], "selected_capability_ids": [], "selected_behavior_ids": ["enemy.behavior.chase_and_melee"]})
    with pytest.raises(WorkflowValidationError, match="do not cover"):
        validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", bad, cs)
    good = parse_selection_output("EntityAbilityBehaviorPlanner", {"selected_entity_ids": ["zombie"], "selected_capability_ids": ENEMY_CHASE_MELEE, "selected_behavior_ids": ["enemy.behavior.chase_and_melee"]})
    validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", good, cs)
    canonical = canonicalize_selection(good)
    assert [entity["entity_id"] for entity in canonical["entities"]] == ["zombie"]
    assert "capabilities" in canonical["entities"][0]
    validate_node_output("EntityAbilityBehaviorPlanner", json.dumps(canonical, ensure_ascii=False))


def _enemy_runtime_selection(entity_id="zombie", behavior_id="enemy.behavior.chase_and_melee", caps=ENEMY_CHASE_MELEE):
    return canonicalize_selection({"selected_entity_ids": [entity_id], "selected_capability_ids": list(caps), "selected_behavior_ids": [behavior_id]})


def test_enemy_runtime_behavior_spec_compiles_to_supported_domain():
    from core.behavior_spec import compile_and_check

    spec, support = compile_and_check(_enemy_runtime_selection())
    assert support["status"] == "supported"
    behavior = spec["behaviors"][0]
    assert behavior["runtime_domain"] == "enemy_runtime"
    assert behavior["bound_entity_id"] == "zombie"
    resolved = {item["capability_id"]: item for item in behavior["resolved_capabilities"]}
    assert set(behavior["required_capability_ids"]) == set(resolved)
    assert resolved["enemy.spawn.spawn_actor"]["params"]["actor_class_path"].startswith("/Game/")
    assert resolved["enemy.attack.melee_hitbox"]["params"]["attack_range"] == 160
    assert {"enemy_spawn_actor", "enemy_detect_player", "enemy_chase_target", "enemy_melee_attack", "enemy_receive_damage", "enemy_emit_death_event", "encounter_complete_when_all_dead"}.issubset({a["type"] for a in behavior["actions"]})


def test_enemy_runtime_codegen_declares_and_renders_required_templates(tmp_path):
    from core.behavior_spec import compile_and_check
    from custom_nodes.template_file_writer import write_files_from_output
    from custom_nodes.typescript_code_generator import build_codegen_output

    spec, support = compile_and_check(_enemy_runtime_selection())
    mapping = {"runtime_mapping_path": "flow/05-puerts-runtime-mapping.json", "behavior_spec_path": "flow/06-behavior-spec.json", "support_check_path": "flow/06-runtime-support-check.json", "runtime_features": support["required_runtime_modules"], "disabled_features": [], "behavior_spec": spec, "support_check": support, "mappings": [{"entity_id": "zombie", "behavior_id": "enemy.behavior.chase_and_melee", "flow_id": "flow_enemy_behavior_chase_and_melee", "runtime_owner": "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts", "implementation_carrier": "template_rendered_ts", "selected_runtime_owner": "AutoUEBehaviorSpec.generated", "existing_framework_candidates": ["AutoUE enemy runtime framework"], "why_not_existing_framework": "requires generated BehaviorSpec plus enemy runtime modules", "temporary_or_canonical": "canonical", "migration_path": "regenerate BehaviorSpec data only", "engine_port_mappings": [], "thin_contracts": ["spawn true enemy actor"], "ability_binding": "behavior_spec:enemy.behavior.chase_and_melee", "verification_evidence": ["EnemySpawned", "EnemyDied", "EncounterCompleted=1"]}], "blocked_mappings": []}
    state = GraphState(save_dir=str(tmp_path), llm_outputs={"PuerTSRuntimeMappingCompiler": json.dumps(mapping), "TypeScriptImplementationSlotProjector": json.dumps({"implementation_slots": []}), "TypeScriptInteractiveTemplatePlanner": json.dumps({"template_inputs": [{"path": "TypeScript/content/generated/interactive/Zombie.ts"}]})})
    output = build_codegen_output(state)
    validate_node_output("TypeScriptRuntimeTemplatePlanner", json.dumps(output, ensure_ascii=False))
    write_files_from_output(state, "TypeScriptRuntimeTemplatePlanner", json.dumps(output, ensure_ascii=False))
    assert (tmp_path / "TypeScript/content/generated/AutoUEEnemyRegistry.ts").exists()
    assert (tmp_path / "TypeScript/content/generated/AutoUEEncounterManager.ts").exists()


def test_docs_exist():
    for filename, heading in [("entities.zh.md", "# 死亡细胞实体库"), ("abilities.zh.md", "# 死亡细胞能力库"), ("behaviors.zh.md", "# 死亡细胞行为库")]:
        text = (DOC_ROOT / filename).read_text(encoding="utf-8")
        assert text.startswith(heading)
        assert "不含音效" in text
        assert "player" in text


def test_twenty_entity_ability_behavior_single_node_fixtures_are_valid():
    runs = sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir())
    assert len(runs) == 20
    for run in runs:
        for filename in ("prompt.txt", "candidate_set.json", "selection_raw.json", "entity_behavior.json", "validation.json"):
            assert (run / filename).exists(), f"{run.name} missing {filename}"
        validation = json.loads((run / "validation.json").read_text(encoding="utf-8"))
        assert validation["result"] == "pass", run.name
        if validation["status"] == "unsupported":
            unsupported_report_path = run / "unsupported_report.json"
            assert unsupported_report_path.exists(), f"{run.name} missing unsupported_report.json"
            unsupported_report = json.loads(unsupported_report_path.read_text(encoding="utf-8"))
            assert unsupported_report["status"] == "unsupported"
            assert unsupported_report["unsupported_capabilities"] or unsupported_report["unsupported_behaviors"]
        selection = json.loads((run / "selection_raw.json").read_text(encoding="utf-8"))
        assert "selected_ability_ids" not in selection
        candidate_set = json.loads((run / "candidate_set.json").read_text(encoding="utf-8"))
        validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", parse_selection_output("EntityAbilityBehaviorPlanner", selection), candidate_set)
        validate_node_output("EntityAbilityBehaviorPlanner", (run / "entity_behavior.json").read_text(encoding="utf-8"))


def test_at_least_one_supported_fixture_has_full_workflow_evidence():
    evidence_files = sorted(FIXTURE_ROOT.glob("*/full_workflow_result.json"))
    assert evidence_files, "missing supported full workflow evidence"
    passed = []
    for path in evidence_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("workflow_result") == "pass" and data.get("validate_output_result") == "pass":
            assert data.get("verification_level") == "full AutoUE workflow + static validate-output; no tsc/PIE claim"
            assert "TypeScriptRuntimeTemplatePlanner" in data.get("validated_llm_nodes", [])
            assert data.get("codegen_files_count", 0) > 0
            passed.append(path)
    assert passed, "full workflow evidence exists but none passed workflow + validate-output"


def test_five_enemy_runtime_case_fixtures_are_static_supported():
    from core.behavior_spec import check_behavior_spec_support

    runs = sorted(path for path in ENEMY_RUNTIME_FIXTURE_ROOT.iterdir() if path.is_dir())
    assert [run.name for run in runs] == ["01-zombie_melee", "02-archer_projectile", "03-kamikaze_self_destruct", "04-shield_bearer_block", "05-room_encounter_multi_enemy"]
    for run in runs:
        for filename in ("candidate_set.json", "selection_raw.json", "entity_behavior.json", "thin_flow.json", "behavior_spec.json", "support_check.json", "typescript_codegen.json", "validation.json"):
            assert (run / filename).exists(), f"{run.name} missing {filename}"
        selection = parse_selection_output("EntityAbilityBehaviorPlanner", json.loads((run / "selection_raw.json").read_text(encoding="utf-8")))
        validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", selection, json.loads((run / "candidate_set.json").read_text(encoding="utf-8")))
        spec = json.loads((run / "behavior_spec.json").read_text(encoding="utf-8"))
        assert check_behavior_spec_support(spec)["status"] == "supported"
        validate_node_output("TypeScriptRuntimeTemplatePlanner", (run / "typescript_codegen.json").read_text(encoding="utf-8"))
        validation = json.loads((run / "validation.json").read_text(encoding="utf-8"))
        assert validation["result"] == "pass"
        assert validation["pie"] == "not_run"
