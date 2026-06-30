from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.behavior_spec import compile_and_check
from core.content_library import build_candidate_set, canonicalize_selection, load_dead_cells_library, validate_selection_against_library_and_candidates
from core.workflow_validation import validate_node_output

OUT_ROOT = ROOT / "tests" / "fixtures" / "dead_cells_eab_runs"

RUNS = [
    ("run_01_zombie_room", "普通牢房：玩家遭遇僵尸，攻击后出现伤害数字、生命条变化，击败后出口解锁。", ["zombie", "level_exit_door", "health_bar_hud", "combat_damage_number_hud"], ["player.combat.attack", "zombie.pursuit.detect_player", "zombie.offense.resolve_hit", "level_exit_door.lock.evaluate_unlock", "health_bar_hud.display.refresh_value", "combat_damage_number_hud.display.refresh_value"]),
    ("run_02_archer_platform", "平台房：弓箭手在高台远程压制，玩家奔跑翻滚接近并攻击，HUD 显示反馈。", ["archer", "combat_damage_number_hud", "minimap_hud"], ["player.movement.run", "player.movement.dodge_roll", "player.combat.attack", "archer.pursuit.detect_player", "archer.offense.resolve_hit", "combat_damage_number_hud.display.refresh_value", "minimap_hud.display.refresh_value"]),
    ("run_03_cursed_chest", "诅咒宝箱房：玩家打开诅咒宝箱获得奖励，同时诅咒计数 HUD 和诅咒特效出现。", ["cursed_chest", "curse_counter_hud", "curse_skull_vfx"], ["cursed_chest.open_reward_and_add_curse", "curse_counter_hud.display.refresh_value", "curse_counter_hud.alert.flash_warning", "curse_skull_vfx.emit.spawn_particles"]),
    ("run_04_poison_pool", "毒池陷阱房：玩家经过毒池，player.effects.poison_dot 和毒粒子反馈出现，生命条持续刷新。", ["poison_pool", "poison_vfx", "health_bar_hud"], ["poison_pool.poison_player_on_overlap", "poison_vfx.emit.spawn_particles", "health_bar_hud.display.refresh_value"]),
    ("run_05_kamikaze_bat", "飞行自爆敌人房：自爆蝙蝠发现玩家后快速接近并爆炸，爆炸特效和伤害数字出现。", ["kamikaze_bat", "burn_vfx", "combat_damage_number_hud"], ["player.movement.dodge_roll", "kamikaze_bat.pursuit.detect_player", "kamikaze_bat.pursuit.close_gap", "kamikaze_bat.offense.resolve_hit", "burn_vfx.emit.spawn_particles", "combat_damage_number_hud.display.refresh_value"]),
    ("run_06_shield_bearer", "持盾兵房：持盾兵正面防御并推进，玩家翻滚绕后攻击，招架火花和图标反馈。", ["shield_bearer", "parry_spark_vfx", "status_icon_hud"], ["player.movement.dodge_roll", "player.combat.attack", "shield_bearer.pursuit.close_gap", "shield_bearer.offense.resolve_hit", "parry_spark_vfx.emit.spawn_particles", "status_icon_hud.display.refresh_value"]),
    ("run_07_flame_trap", "喷火陷阱走廊：喷火陷阱预警后进入激活窗口，玩家等待冷却后通过，燃烧特效出现。", ["flame_jet_trap", "burn_vfx"], ["flame_jet_trap.arming.show_warning", "flame_jet_trap.arming.enter_active", "flame_jet_trap.apply_burn_on_hit", "burn_vfx.emit.spawn_particles", "player.movement.run"]),
    ("run_08_elite_slasher", "精英斩杀者房：精英斩杀者带光环追击，重攻击预警明显，玩家连击攻击并触发暴击特效。", ["slasher", "elite_aura_vfx", "critical_hit_vfx", "combat_damage_number_hud"], ["player.combat.attack", "slasher.pursuit.detect_player", "slasher.pursuit.close_gap", "slasher.offense.resolve_hit", "elite_aura_vfx.emit.attach_to_target", "critical_hit_vfx.emit.spawn_particles"]),
    ("run_09_concierge_boss", "看守者 Boss 房：看守者阶段化攻击，Boss 血条刷新，玩家翻滚躲避并攻击。", ["concierge_boss", "boss_health_bar_hud", "critical_hit_vfx"], ["player.movement.dodge_roll", "player.combat.attack", "concierge_boss.pursuit.detect_player", "concierge_boss.offense.resolve_hit", "boss_health_bar_hud.display.refresh_value", "critical_hit_vfx.emit.spawn_particles"]),
    ("run_10_teleporter_room", "传送器房：玩家使用生物群落传送器切换房间，传送特效播放，小地图更新。", ["biome_teleporter", "teleport_vfx", "minimap_hud"], ["biome_teleporter.activate_transition", "teleport_vfx.emit.spawn_particles", "minimap_hud.display.refresh_value"]),
    ("run_11_scroll_reward", "卷轴奖励房：玩家拾取力量卷轴和细胞，奖励视觉反馈出现，HUD 图标刷新。", ["scroll_power_pickup", "cell_pickup", "status_icon_hud"], ["scroll_power_pickup.collect.detect_pickup", "scroll_power_pickup.collect.grant_reward", "cell_pickup.collect.grant_reward", "scroll_power_pickup.feedback.spawn_reward_visual", "status_icon_hud.display.refresh_value"]),
    ("run_12_shop_forge", "商店和铸造所房间：玩家与商人和铸造所交易，购买或升级装备，金币 HUD 相关反馈刷新。", ["shop_room_vendor", "forge_station", "gold_pickup", "status_icon_hud"], ["shop_room_vendor.purchase_item", "forge_station.apply_item_upgrade", "status_icon_hud.display.refresh_value"]),
    ("run_13_saw_platform", "锯刃平台房：移动锯刃陷阱和塌陷地板迫使玩家跳跃奔跑，生命条在受伤时刷新。", ["saw_blade_trap", "crumbling_floor", "health_bar_hud"], ["player.movement.run", "player.movement.dodge_roll", "saw_blade_trap.arming.enter_active", "saw_blade_trap.damage.apply_contact", "crumbling_floor.collapse_when_touched", "health_bar_hud.display.refresh_value"]),
    ("run_14_exit_unlock", "出口解锁房：击败敌人后出口门从锁定变为可进入，出口完成关卡切换。", ["zombie", "level_exit_door", "status_icon_hud"], ["player.combat.attack", "zombie.offense.resolve_hit", "level_exit_door.lock.evaluate_unlock", "level_exit_door.transition.accept_entry", "level_exit_door.transition.finish_transition", "status_icon_hud.alert.flash_warning"]),
    ("run_15_bleed_build", "流血构筑房：血之刃攻击敌人写入 target.effects.bleed_dot，流血特效持续跳动，伤害数字刷新。", ["blood_sword", "zombie", "bleed_vfx", "combat_damage_number_hud"], ["blood_sword.apply_bleed_on_hit", "player.combat.attack", "zombie.offense.resolve_hit", "bleed_vfx.emit.spawn_particles", "combat_damage_number_hud.display.refresh_value"]),
    ("run_16_freeze_control", "冰冻控制房：玩家走入冰冻陷阱，player.effects.frozen 阻止移动，冰冻特效显示并触发侧视角镜头震动。", ["player", "freeze_trap", "freeze_vfx", "side_camera"], ["freeze_trap.freeze_player_on_overlap"]),
    ("run_17_electric_chain", "电击连锁房：电鞭命中多个敌人，target.effects.shocked 和电弧特效连锁，伤害数字出现。", ["electric_whip", "inquisitor", "electric_vfx", "combat_damage_number_hud"], ["electric_whip.apply_shock_chain", "player.combat.attack", "inquisitor.pursuit.detect_player", "electric_vfx.emit.spawn_particles", "combat_damage_number_hud.display.refresh_value"]),
    ("run_18_gold_cell_reward", "奖励房：敌人死亡掉落金币和细胞，玩家收集后奖励视觉反馈和 HUD 图标刷新。", ["gold_pickup", "cell_pickup", "corpse_dust_vfx", "status_icon_hud"], ["gold_pickup.collect.detect_pickup", "gold_pickup.collect.grant_reward", "cell_pickup.collect.detect_pickup", "cell_pickup.collect.grant_reward", "corpse_dust_vfx.emit.spawn_particles", "status_icon_hud.display.refresh_value"]),
    ("run_19_hud_state", "HUD 密集反馈：玩家同时受到诅咒、中毒和冷却限制，生命条、诅咒计数、图标和冷却计时 HUD 更新。", ["health_bar_hud", "curse_counter_hud", "status_icon_hud", "cooldown_meter_hud"], ["cursed_chest.open_reward_and_add_curse", "poison_pool.poison_player_on_overlap", "health_bar_hud.display.refresh_value", "curse_counter_hud.display.refresh_value", "status_icon_hud.display.refresh_value", "cooldown_meter_hud.display.refresh_value", "curse_counter_hud.alert.flash_warning"]),
    ("run_20_vfx_showcase", "特效展示战斗：暴击、燃烧、中毒、冰冻和死亡消散粒子连续出现，玩家攻击并清理敌人。", ["zombie", "critical_hit_vfx", "burn_vfx", "poison_vfx", "freeze_vfx", "corpse_dust_vfx"], ["player.combat.attack", "zombie.offense.resolve_hit", "critical_hit_vfx.emit.spawn_particles", "burn_vfx.emit.spawn_particles", "poison_vfx.emit.spawn_particles", "freeze_vfx.emit.spawn_particles", "corpse_dust_vfx.emit.spawn_particles"]),
]


def thin_for(canonical: dict) -> dict:
    lib = load_dead_cells_library()
    flows = []
    for entity in canonical.get("entities", []):
        for ability in entity.get("abilities", []):
            for behavior in ability.get("behaviors", []):
                behavior_id = behavior["behavior_id"]
                ports = []
                for cap_id in behavior.get("required_capability_ids", []):
                    for port in lib["capabilities"].get(cap_id, {}).get("engine_ports", []):
                        if port not in ports:
                            ports.append(port)
                if not ports:
                    ports = ["manual.trigger"]
                flows.append({
                    "flow_id": "flow_" + behavior_id.replace(".", "_"),
                    "entity_id": behavior["entity_id"],
                    "ability_id": behavior["ability_id"],
                    "source_behavior_id": behavior_id,
                    "stages": [{"stage": "Event/Result", "contract": "compile behavior spec", "inputs": ["trigger"], "outputs": ["actions"], "engine_ports": ports}],
                    "verification": behavior.get("verification_logs", [f"BehaviorTriggered {behavior_id}"]),
                })
    return {"flows": flows}


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary = []
    lib = load_dead_cells_library()
    for index, (run_name, prompt, entity_ids, behavior_ids) in enumerate(RUNS, start=1):
        missing = [bid for bid in behavior_ids if bid not in lib["behaviors"]]
        if missing:
            raise RuntimeError(f"{run_name}: unknown behavior ids: {missing}")
        run_root = OUT_ROOT / f"{index:02d}-{run_name}"
        run_root.mkdir(parents=True, exist_ok=True)
        query = prompt + "\n" + " ".join(entity_ids + behavior_ids)
        candidate_set = build_candidate_set(query)
        selection = {"selected_entity_ids": entity_ids, "selected_capability_ids": [], "selected_behavior_ids": behavior_ids}
        validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", selection, candidate_set)
        canonical = canonicalize_selection(selection)
        validate_node_output("EntityAbilityBehaviorPlanner", json.dumps(canonical, ensure_ascii=False))
        thin = thin_for(canonical)
        behavior_spec, support_check = compile_and_check(canonical, thin)
        status = support_check["status"]
        for name, obj in [
            ("candidate_set.json", candidate_set),
            ("selection_raw.json", selection),
            ("entity_behavior.json", canonical),
            ("thin_flow.json", thin),
            ("behavior_spec.json", behavior_spec),
            ("support_check.json", support_check),
        ]:
            (run_root / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_root / "prompt.txt").write_text(prompt, encoding="utf-8")
        validation = {
            "result": "pass",
            "status": status,
            "support_status": status,
            "unsupported_capabilities": support_check.get("unsupported_capabilities", []),
            "unsupported_behaviors": support_check.get("unsupported_behaviors", []),
            "generated_runtime": "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts" if status == "supported" else None,
            "blocked_reason": None if status == "supported" else "unsupported capability in RuntimeSupportMatrix",
        }
        if status == "supported":
            result = {
                "result": "supported",
                "behavior_count": len(behavior_spec.get("behaviors", [])),
                "generated_runtime": "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts",
                "validate_output": "actual workflow validate-output must be run outside this fixture generator",
            }
            (run_root / "full_workflow_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            validation["full_workflow_result"] = "full_workflow_result.json"
        else:
            report = {"result": "unsupported", "unsupported_behaviors": support_check.get("unsupported_behaviors", []), "unsupported_capabilities": support_check.get("unsupported_capabilities", [])}
            (run_root / "unsupported_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            validation["unsupported_report"] = "unsupported_report.json"
        (run_root / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
        summary.append({"run": f"{index:02d}-{run_name}", "status": status, "unsupported_behaviors": support_check.get("unsupported_behaviors", [])})
    (OUT_ROOT / "SUMMARY.json").write_text(json.dumps({"schema_version": "autoue-dead-cells-20-runs/v1", "runs": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"result": "pass", "runs": len(RUNS), "supported": sum(1 for r in summary if r["status"] == "supported"), "unsupported": sum(1 for r in summary if r["status"] == "unsupported"), "root": str(OUT_ROOT)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
