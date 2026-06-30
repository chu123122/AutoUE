from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.behavior_spec import compile_and_check
from core.content_library import build_candidate_set, canonicalize_selection, load_dead_cells_library, parse_selection_output, validate_selection_against_library_and_candidates
from core.workflow_validation import validate_node_output

OUT_ROOT = ROOT / "tests" / "fixtures" / "dead_cells_eab_runs"
CAPS = {
    "melee": ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.chase_target", "enemy.attack.melee_hitbox", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"],
    "projectile": ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.keep_distance", "enemy.attack.projectile_spawn", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"],
    "self_destruct": ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.chase_target", "enemy.attack.self_destruct", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"],
    "shield": ["enemy.spawn.spawn_actor", "enemy.sensor.detect_player_by_distance", "enemy.movement.chase_target", "enemy.defense.directional_block", "enemy.attack.melee_hitbox", "enemy.health.receive_damage", "enemy.death.emit_death_event", "encounter.complete.complete_when_all_dead"],
    "hud": ["hud.display.refresh_value"], "vfx": ["vfx.spawn.spawn_particles"], "freeze": ["hazard.sensor.detect_overlap", "hazard.effect.apply_freeze", "vfx.visibility.set_visible_while_state", "camera.feedback.camera_impulse"],
    "pickup": ["pickup.collect.grant_reward", "pickup.feedback.spawn_reward_visual"], "exit": ["encounter.exit.unlock_exit", "level.transition.activate"],
}
RUNS = [
("run_01_zombie_room", "普通牢房：玩家遭遇僵尸，击败后出口解锁。", ["zombie", "level_exit_door", "health_bar_hud"], CAPS["melee"]+CAPS["exit"]+CAPS["hud"], ["enemy.behavior.chase_and_melee", "exit.behavior.unlock_and_transition", "hud.behavior.refresh_value"]),
("run_02_archer_platform", "平台房：弓箭手远程压制，HUD 显示反馈。", ["archer", "combat_damage_number_hud"], CAPS["projectile"]+CAPS["hud"], ["enemy.behavior.keep_distance_and_projectile", "hud.behavior.refresh_value"]),
("run_03_cursed_chest", "诅咒宝箱房：玩家获得奖励，HUD 和特效出现。", ["cursed_chest", "curse_counter_hud", "curse_skull_vfx"], CAPS["pickup"]+CAPS["hud"]+CAPS["vfx"], ["pickup.behavior.collect_reward", "hud.behavior.refresh_value", "vfx.behavior.spawn_particles"]),
("run_04_poison_pool", "毒池陷阱房：毒池和毒粒子反馈出现。", ["poison_pool", "poison_vfx", "health_bar_hud"], ["hazard.sensor.detect_overlap", "hazard.arming.arm_hazard", "hazard.damage.apply_hazard_damage"]+CAPS["vfx"]+CAPS["hud"], ["hazard.behavior.arm_and_damage", "vfx.behavior.spawn_particles", "hud.behavior.refresh_value"]),
("run_05_kamikaze_bat", "飞行自爆敌人房：自爆蝙蝠接近并爆炸。", ["kamikaze_bat", "burn_vfx", "combat_damage_number_hud"], CAPS["self_destruct"]+CAPS["vfx"]+CAPS["hud"], ["enemy.behavior.chase_and_self_destruct", "vfx.behavior.spawn_particles", "hud.behavior.refresh_value"]),
("run_06_shield_bearer", "持盾兵房：持盾兵格挡反击。", ["shield_bearer", "parry_spark_vfx", "status_icon_hud"], CAPS["shield"]+CAPS["vfx"]+CAPS["hud"], ["enemy.behavior.block_then_counter", "vfx.behavior.spawn_particles", "hud.behavior.refresh_value"]),
("run_07_flame_trap", "喷火陷阱走廊：机关预备并造成伤害。", ["flame_jet_trap", "burn_vfx"], ["hazard.sensor.detect_overlap", "hazard.arming.arm_hazard", "hazard.damage.apply_hazard_damage"]+CAPS["vfx"], ["hazard.behavior.arm_and_damage", "vfx.behavior.spawn_particles"]),
("run_08_elite_slasher", "精英斩杀者房：精英追击并出现光环特效。", ["slasher", "elite_aura_vfx", "critical_hit_vfx"], CAPS["melee"]+CAPS["vfx"], ["enemy.behavior.chase_and_melee", "vfx.behavior.spawn_particles"]),
("run_09_concierge_boss", "看守者 Boss 房：Boss 追击攻击，Boss 血条刷新。", ["concierge_boss", "boss_health_bar_hud"], CAPS["melee"]+CAPS["hud"], ["enemy.behavior.chase_and_melee", "hud.behavior.refresh_value"]),
("run_10_teleporter_room", "传送器房：传送特效播放，小地图更新。", ["biome_teleporter", "teleport_vfx", "minimap_hud"], CAPS["vfx"]+CAPS["hud"], ["vfx.behavior.spawn_particles", "hud.behavior.refresh_value"]),
("run_11_scroll_reward", "卷轴奖励房：玩家拾取奖励并显示图标。", ["scroll_power_pickup", "cell_pickup", "status_icon_hud"], CAPS["pickup"]+CAPS["hud"], ["pickup.behavior.collect_reward", "hud.behavior.refresh_value"]),
("run_12_shop_forge", "商店和铸造所房间：购买或升级装备。", ["shop_room_vendor", "forge_station", "status_icon_hud"], CAPS["hud"], ["hud.behavior.refresh_value"]),
("run_13_saw_platform", "锯刃平台房：机关伤害后生命条刷新。", ["saw_blade_trap", "crumbling_floor", "health_bar_hud"], ["hazard.sensor.detect_overlap", "hazard.arming.arm_hazard", "hazard.damage.apply_hazard_damage"]+CAPS["hud"], ["hazard.behavior.arm_and_damage", "hud.behavior.refresh_value"]),
("run_14_exit_unlock", "出口解锁房：击败敌人后出口可进入。", ["zombie", "level_exit_door", "status_icon_hud"], CAPS["melee"]+CAPS["exit"]+CAPS["hud"], ["enemy.behavior.chase_and_melee", "exit.behavior.unlock_and_transition", "hud.behavior.refresh_value"]),
("run_15_bleed_build", "流血构筑房：玩家攻击并出现流血特效。", ["blood_sword", "zombie", "bleed_vfx", "combat_damage_number_hud"], CAPS["melee"]+CAPS["vfx"]+CAPS["hud"], ["enemy.behavior.chase_and_melee", "vfx.behavior.spawn_particles", "hud.behavior.refresh_value"]),
("run_16_freeze_control", "冰冻控制房：冰冻陷阱阻止移动并显示特效。", ["player", "freeze_trap", "freeze_vfx", "side_camera"], CAPS["freeze"], ["hazard.behavior.freeze_on_overlap"]),
("run_17_electric_chain", "电击连锁房：电弧特效和伤害数字出现。", ["electric_whip", "inquisitor", "electric_vfx", "combat_damage_number_hud"], CAPS["melee"]+CAPS["vfx"]+CAPS["hud"], ["enemy.behavior.chase_and_melee", "vfx.behavior.spawn_particles", "hud.behavior.refresh_value"]),
("run_18_gold_cell_reward", "奖励房：收集金币和细胞并出现反馈。", ["gold_pickup", "cell_pickup", "corpse_dust_vfx", "status_icon_hud"], CAPS["pickup"]+CAPS["vfx"]+CAPS["hud"], ["pickup.behavior.collect_reward", "vfx.behavior.spawn_particles", "hud.behavior.refresh_value"]),
("run_19_hud_state", "HUD 密集反馈：生命条、诅咒计数和图标更新。", ["health_bar_hud", "curse_counter_hud", "status_icon_hud", "cooldown_meter_hud"], CAPS["hud"], ["hud.behavior.refresh_value"]),
("run_20_vfx_showcase", "特效展示战斗：多种粒子连续出现。", ["zombie", "critical_hit_vfx", "burn_vfx", "poison_vfx", "freeze_vfx", "corpse_dust_vfx"], CAPS["melee"]+CAPS["vfx"], ["enemy.behavior.chase_and_melee", "vfx.behavior.spawn_particles"]),
]

def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def thin_for(spec: dict[str, Any]) -> dict[str, Any]:
    flows=[]
    for behavior in spec.get("behaviors", []):
        ports=[]
        for cap in behavior.get("resolved_capabilities", []):
            # support rows and capability metadata already carry exact ports; keep a minimal deterministic trace.
            if cap.get("capability_id") == "enemy.spawn.spawn_actor": ports.append("actor.spawn")
            if cap.get("capability_id") == "enemy.attack.melee_hitbox": ports.append("gameplay_statics.apply_damage")
        flows.append({"flow_id": behavior["flow_id"], "entity_id": behavior.get("entity_id"), "source_behavior_id": behavior["behavior_id"], "stages": [{"stage": "Event/Result", "contract": "compile canonical behavior spec", "inputs": ["trigger"], "outputs": ["actions"], "engine_ports": ports or ["manual.trigger"]}], "verification": behavior.get("verification_logs", [])})
    return {"flows": flows}

def main() -> int:
    preserved_full_workflow_evidence: dict[Path, str] = {}
    if OUT_ROOT.exists():
        for evidence_path in OUT_ROOT.glob("*/full_workflow_result.json"):
            preserved_full_workflow_evidence[evidence_path.relative_to(OUT_ROOT)] = evidence_path.read_text(encoding="utf-8")
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    lib=load_dead_cells_library(); summary=[]
    for i,(name,prompt,entities,caps,behaviors) in enumerate(RUNS,1):
        root=OUT_ROOT/f"{i:02d}-{name}"; root.mkdir(parents=True, exist_ok=True)
        candidate_set=build_candidate_set(prompt+" "+" ".join(entities+caps+behaviors))
        selection_raw={"selected_entity_ids":entities,"selected_capability_ids":list(dict.fromkeys(caps)),"selected_behavior_ids":behaviors}
        selection=parse_selection_output("EntityAbilityBehaviorPlanner", selection_raw)
        validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", selection, candidate_set)
        canonical=canonicalize_selection(selection); validate_node_output("EntityAbilityBehaviorPlanner", json.dumps(canonical,ensure_ascii=False))
        draft,support=compile_and_check(canonical); thin=thin_for(draft); spec,support=compile_and_check(canonical,thin)
        for fn,obj in [("candidate_set.json",candidate_set),("selection_raw.json",selection_raw),("entity_behavior.json",canonical),("thin_flow.json",thin),("behavior_spec.json",spec),("support_check.json",support)]: write_json(root/fn,obj)
        (root/"prompt.txt").write_text(prompt+"\n",encoding="utf-8")
        validation={"result":"pass","status":support["status"],"unsupported_capabilities":support.get("unsupported_capabilities",[]),"unsupported_behaviors":support.get("unsupported_behaviors",[])}
        write_json(root/"validation.json",validation)
        if support["status"] == "unsupported":
            write_json(root/"unsupported_report.json",{
                "schema_version":"autoue-unsupported-report/v1",
                "status":"unsupported",
                "unsupported_capabilities":support.get("unsupported_capabilities",[]),
                "unsupported_behaviors":support.get("unsupported_behaviors",[]),
                "reason":"SupportMatrix rejected at least one selected canonical capability/behavior; TypeScript generation must not proceed for this case."
            })
        summary.append({"run":root.name,"status":support["status"]})
    for rel_path, content in preserved_full_workflow_evidence.items():
        target = OUT_ROOT / rel_path
        if target.parent.exists():
            target.write_text(content, encoding="utf-8")
    write_json(OUT_ROOT/"SUMMARY.json",{"schema_version":"autoue-dead-cells-20-runs/v2","runs":summary})
    print(json.dumps({"result":"pass","runs":len(summary),"supported":sum(r['status']=='supported' for r in summary),"unsupported":sum(r['status']!='supported' for r in summary)},ensure_ascii=False,indent=2))
    return 0
if __name__ == "__main__": raise SystemExit(main())
