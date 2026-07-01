from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.BaseLLMNode import GraphState
from core.behavior_spec import compile_and_check
from core.content_library import build_candidate_set, canonicalize_selection, parse_selection_output, validate_selection_against_library_and_candidates
from custom_nodes.typescript_code_generator import build_codegen_output

OUT = ROOT / "tests" / "fixtures" / "dead_cells_enemy_runtime_cases"
MELEE=["enemy.spawn.spawn_actor","enemy.sensor.detect_player_by_distance","enemy.movement.chase_target","enemy.attack.melee_hitbox","enemy.health.receive_damage","enemy.death.emit_death_event","encounter.complete.complete_when_all_dead"]
PROJECTILE=["enemy.spawn.spawn_actor","enemy.sensor.detect_player_by_distance","enemy.movement.keep_distance","enemy.attack.projectile_spawn","enemy.health.receive_damage","enemy.death.emit_death_event","encounter.complete.complete_when_all_dead"]
SELF=["enemy.spawn.spawn_actor","enemy.sensor.detect_player_by_distance","enemy.movement.chase_target","enemy.attack.self_destruct","enemy.health.receive_damage","enemy.death.emit_death_event","encounter.complete.complete_when_all_dead"]
SHIELD=["enemy.spawn.spawn_actor","enemy.sensor.detect_player_by_distance","enemy.movement.chase_target","enemy.defense.directional_block","enemy.attack.melee_hitbox","enemy.health.receive_damage","enemy.death.emit_death_event","encounter.complete.complete_when_all_dead"]
CASES=[
("01-zombie_melee","僵尸近战 canonical prototype runtime",["zombie"],MELEE,["enemy.behavior.chase_and_melee"]),
("02-archer_projectile","弓箭手远程 canonical prototype runtime",["archer"],PROJECTILE,["enemy.behavior.keep_distance_and_projectile"]),
("03-kamikaze_self_destruct","自爆蝙蝠 canonical prototype runtime",["kamikaze_bat"],SELF,["enemy.behavior.chase_and_self_destruct"]),
("04-shield_bearer_block","持盾兵 canonical prototype runtime",["shield_bearer"],SHIELD,["enemy.behavior.block_then_counter"]),
("05-room_encounter_multi_enemy","多敌人 canonical prototype runtime",["zombie","archer","kamikaze_bat","shield_bearer"],list(dict.fromkeys(MELEE+PROJECTILE+SELF+SHIELD)),["enemy.behavior.chase_and_melee","enemy.behavior.keep_distance_and_projectile","enemy.behavior.chase_and_self_destruct","enemy.behavior.block_then_counter"]),
]
PORTS={"enemy_spawn_actor":["actor.spawn"],"enemy_detect_player":["actor.get_distance_to"],"enemy_chase_target":["actor.set_actor_location"],"enemy_keep_distance":["actor.set_actor_location"],"enemy_melee_attack":["kismet.sphere_trace_single","gameplay_statics.apply_damage"],"enemy_projectile_attack":["projectile.spawn"],"enemy_self_destruct":["gameplay_statics.apply_damage","actor.destroy"],"enemy_directional_block":["actor.get_forward_vector"],"enemy_receive_damage":["actor.on_take_any_damage"],"enemy_emit_death_event":["actor.on_destroyed"],"encounter_complete_when_all_dead":["encounter.alive_count"]}

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def thin_flow_for(spec: dict[str, Any]) -> dict[str, Any]:
    flows=[]
    for b in spec["behaviors"]:
        stages=[]
        for a in b["actions"]:
            ports=PORTS.get(a["type"],[])
            if ports: stages.append({"stage":"Runtime","contract":f"{a['type']} for {b['behavior_id']}","inputs":["BehaviorSpec","runtime_params"],"outputs":[a["type"]],"engine_ports":ports})
        flows.append({"flow_id":b["flow_id"],"entity_id":b["entity_id"],"source_behavior_id":b["behavior_id"],"stages":stages,"verification":["EnemySpawned","EnemyDied","EncounterCompleted=1"]})
    return {"flows":flows}

def codegen_for(spec: dict[str, Any], support: dict[str, Any]) -> dict[str, Any]:
    composition = [{"enemy": str(behavior.get("entity_id") or behavior.get("bound_entity_id") or "zombie"), "count": 1} for behavior in spec.get("behaviors", [])]
    encounter_spec = {"schema_version": "autoue-encounter-spec/v1", "encounters": [{"encounter_id": "room_01_initial_guard", "trigger": {"type": "on_level_start"}, "spawn_group": "room_01_guard", "enemy_budget": max(1, len(composition)), "composition": composition or [{"enemy": "zombie", "count": 1}], "spawn_policy": {"avoid_camera_view": False, "min_distance_to_player": 400, "consume_spawn_point": True, "max_alive": max(1, len(composition))}, "completion": {"type": "all_spawned_enemies_defeated", "set_flags": ["enemy_defeated", "exit_unlocked"]}}]}
    required_modules = ["encounter_spec_data", "spawn_point_registry", "enemy_spawn_manager"]
    runtime_features = list(support["required_runtime_modules"])
    for module in required_modules:
        if module not in runtime_features:
            runtime_features.append(module)
    mapping={"runtime_mapping_path":"flow/05-puerts-runtime-mapping.json","behavior_spec_path":"flow/06-behavior-spec.json","support_check_path":"flow/06-runtime-support-check.json","encounter_spec_path":"flow/03-encounter-spec.json","scene_spawn_manifest_path":"flow/scene-spawn-manifest.json","runtime_features":runtime_features,"disabled_features":[],"behavior_spec":spec,"encounter_spec":encounter_spec,"support_check":support,"mappings":[],"blocked_mappings":[]}
    state=GraphState(llm_outputs={"PuerTSRuntimeMappingCompiler":json.dumps(mapping,ensure_ascii=False),"TypeScriptImplementationSlotProjector":json.dumps({"implementation_slots":[]}),"TypeScriptInteractiveTemplatePlanner":json.dumps({"template_inputs":[{"path":"TypeScript/content/generated/interactive/EnemyRuntimeHarness.ts"}]})})
    return build_codegen_output(state)

def main() -> int:
    OUT.mkdir(parents=True,exist_ok=True)
    for name,prompt,entities,caps,behaviors in CASES:
        root=OUT/name; root.mkdir(parents=True,exist_ok=True); (root/"prompt.txt").write_text(prompt+"\n",encoding="utf-8")
        cs=build_candidate_set(prompt+" "+" ".join(entities+caps+behaviors))
        raw={"selected_entity_ids":entities,"selected_capability_ids":caps,"selected_behavior_ids":behaviors}
        sel=parse_selection_output("EntityAbilityBehaviorPlanner",raw); validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner",sel,cs)
        eb=canonicalize_selection(sel); draft,_=compile_and_check(eb); thin=thin_flow_for(draft); spec,support=compile_and_check(eb,thin)
        if support["status"]!="supported": raise RuntimeError(f"{name}: expected supported, got {support}")
        cg=codegen_for(spec,support)
        for fn,obj in [("candidate_set.json",cs),("selection_raw.json",raw),("entity_behavior.json",eb),("thin_flow.json",thin),("behavior_spec.json",spec),("support_check.json",support),("typescript_codegen.json",cg),("validation.json",{"result":"pass","verification_level":"repo-level static","tsc":"not_run","pie":"not_run"})]: write_json(root/fn,obj)
    print(json.dumps({"result":"pass","cases":len(CASES),"output":str(OUT)},ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
